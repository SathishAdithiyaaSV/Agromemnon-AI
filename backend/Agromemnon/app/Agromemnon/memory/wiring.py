"""Wiring for AgentCore Memory: durable history plus cross-chat recall.

Two separate concerns, deliberately built from two different objects:

*Short-term, within one conversation.* `AgentCoreMemorySessionManager` persists every
turn to AgentCore Memory as an event and replays them when the agent is constructed.
This is what makes a cold start invisible: before it, history lived only in the
process, so a restart silently wiped the conversation while the farmer's screen still
showed it.

*Long-term, across conversations.* AgentCore's strategies read those same events
server-side and distil them into memory records — preferences, durable facts, a
summary per conversation. `MemoryManager` reads those records back through
recall-only stores, injecting the relevant ones before each turn and exposing a
recall tool the orchestrator can call deliberately.

ONE WRITER, THREE READERS — this topology is load-bearing.

`create_event` writes to the (memory, actor, session) stream, not to a namespace, so
any two writers duplicate every event and extraction then runs twice over the same
turns. The session manager is therefore the only writer, and every store here is
recall-only (`writable=False`, no extraction). Strands' own store factory enforces
the same rule and raises when more than one store is writable. For the same reason
the `add_memory` tool stays off: writes are the extraction strategies' job, and a
model-written record would bypass them.

Retrieval is configured in exactly one place too. The session manager can inject
long-term context itself via `retrieval_config`, but that would inject alongside
`MemoryManager` and put two copies of the same records in front of the model, so it
is left unset and `MemoryManager` owns retrieval.

Nothing here is required. If no memory is configured the helpers return None and the
agent runs exactly as it did before — in-process history, no recall. A hackathon demo
that cannot start because a memory resource is missing is worse than one without
memory, and local development has no AgentCore Memory at all.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Namespace templates. These MUST match the strategy namespaceTemplates in
# agentcore/agentcore.json: the strategies decide where records are written and
# these decide where they are read from, and a mismatch is silent — retrieval just
# returns nothing, which looks exactly like a farmer with no history yet.
PROFILE_NAMESPACE = "farmer/{actorId}/profile"
FACTS_NAMESPACE = "farmer/{actorId}/facts"
CHAT_NAMESPACE = "farmer/{actorId}/chats/{sessionId}"
# The summaries are written one namespace per conversation, so cross-chat recall has
# to read the parent and every child under it. That subtree read is the whole trick
# behind "remembers what we discussed last month".
CHATS_PATH = "farmer/{actorId}/chats"

# A record scoring below this is likelier to mislead than to help: the farmer sees a
# confident reference to something they never said.
MIN_RELEVANCE = 0.4

_memory_id: str | None = None
_resolved = False


def region() -> str | None:
    """Region holding the memory resource, if it differs from the runtime's."""
    return os.environ.get("AGENTCORE_MEMORY_REGION") or os.environ.get("AWS_REGION")


def memory_id() -> str | None:
    """Resolve the AgentCore Memory id once per process, or None if unavailable.

    `AGENTCORE_MEMORY_ID` wins when set. Otherwise the id is looked up by name,
    because CloudFormation assigns it at create time (`<name>-<suffix>`) and there is
    no way to know it while writing the config that deploys it. Resolving by name
    means a deploy needs no follow-up step to paste an id back into envVars, which is
    one fewer thing to get wrong on demo day.

    The result — including failure — is cached, so a missing or unreachable memory
    costs one control-plane call per container rather than one per turn.
    """
    global _memory_id, _resolved
    if _resolved:
        return _memory_id
    _resolved = True

    configured = (os.environ.get("AGENTCORE_MEMORY_ID") or "").strip()
    if configured:
        _memory_id = configured
        return _memory_id

    name = (os.environ.get("AGENTCORE_MEMORY_NAME") or "").strip()
    if not name:
        logger.info("No AGENTCORE_MEMORY_ID or AGENTCORE_MEMORY_NAME set; memory disabled.")
        return None

    try:
        from bedrock_agentcore.memory.client import MemoryClient

        client = MemoryClient(region_name=region())
        # The service reports the id as "<name>-<suffix>", which is how the SDK
        # matches it internally too.
        match = next((m for m in client.list_memories() if str(m.get("id", "")).startswith(name)), None)
        if match is None:
            logger.warning("No AgentCore Memory named %r found; memory disabled.", name)
            return None
        _memory_id = match["id"]
        logger.info("Resolved AgentCore Memory %r to %s", name, _memory_id)
    except Exception:
        # Denied IAM, wrong region, service unavailable — none of it should stop the
        # farmer getting an answer.
        logger.warning("Could not resolve AgentCore Memory by name; memory disabled.", exc_info=True)
        _memory_id = None
    return _memory_id


def build_session_manager(context) -> Any | None:
    """Durable short-term history for one conversation, or None when unavailable.

    `async_mode=True` because the entrypoint drives the agent with `stream_async`:
    without it, every persisted turn runs a blocking boto3 call on the event loop and
    stalls the token stream the farmer is watching.

    `filter_restored_tool_context=True` drops historical toolUse/toolResult blocks
    when replaying. Those blocks are only meaningful paired with the call that
    produced them, and replaying half a pair is what makes a model reject the
    restored history outright — the same failure `strip_trailing_tool_use` guards
    against on the way in.
    """
    resolved = memory_id()
    if not resolved:
        return None

    try:
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )

        config = AgentCoreMemoryConfig(
            memory_id=resolved,
            actor_id=context.actor_id,
            session_id=context.session_id,
            # Retrieval belongs to MemoryManager; see the module docstring.
            retrieval_config=None,
            filter_restored_tool_context=True,
            async_mode=True,
        )
        return AgentCoreMemorySessionManager(agentcore_memory_config=config, region_name=region())
    except Exception:
        logger.warning("Could not attach AgentCore Memory session manager.", exc_info=True)
        return None


def build_memory_manager(context) -> Any | None:
    """Cross-chat recall over the farmer's own long-term records, or None.

    Three stores, one per strategy, because a strategy's records answer a different
    kind of question and the model benefits from knowing which is which: a stated
    preference is not the same claim as a fact extracted from a past answer, and
    neither is the same as last month's conversation summary. The store name travels
    with each entry into the injected block, so the model can weigh them.
    """
    resolved = memory_id()
    if not resolved:
        return None

    try:
        from bedrock_agentcore.memory.integrations.strands.memorystore import AgentCoreMemoryStore
        from strands.memory import MemoryManager

        shared = dict(
            memory_id=resolved,
            actor_id=context.actor_id,
            session_id=context.session_id,
            region_name=region(),
            writable=False,
            extraction=None,
            min_score=MIN_RELEVANCE,
        )
        stores = [
            AgentCoreMemoryStore(
                name="farmer_preferences",
                description=(
                    "How this farmer prefers to farm and be advised: crops they grow, "
                    "irrigation they have, land size, language."
                ),
                namespace=PROFILE_NAMESPACE,
                max_search_results=4,
                **shared,
            ),
            AgentCoreMemoryStore(
                name="farm_facts",
                description=(
                    "Durable facts this farmer has stated before: soil health card readings, "
                    "plot sizes, sowing dates, schemes already applied for, past problems."
                ),
                namespace=FACTS_NAMESPACE,
                max_search_results=5,
                **shared,
            ),
            AgentCoreMemoryStore(
                name="past_conversations",
                description="Summaries of this farmer's earlier conversations with the service.",
                namespace_path=CHATS_PATH,
                max_search_results=3,
                **shared,
            ),
        ]

        return MemoryManager(
            stores=stores,
            search_tool_config={
                "name": "recall_farmer_history",
                "description": (
                    "Search what this farmer has told the service before — their soil readings, "
                    "plot sizes, crops, irrigation, schemes applied for, and earlier "
                    "conversations. Use it when the farmer refers back to something ('the field "
                    "I asked about', 'the same crop as last time'), when a needed detail such as "
                    "land size or a soil reading is missing, or to check whether advice already "
                    "given should be followed up. Returns the farmer's own past statements, not "
                    "agricultural data: never quote a price, dose or forecast from it."
                ),
            },
            # Writes belong to the extraction strategies; see the module docstring.
            add_tool_config=False,
            injection={
                # Inject on a fresh ask only. On tool-result turns the farmer's question
                # is already in context and re-injecting just crowds the tool output.
                "trigger": "userTurn",
                "max_entries": 5,
            },
        )
    except Exception:
        logger.warning("Could not attach AgentCore Memory recall.", exc_info=True)
        return None
