import asyncio
from typing import Any
from collections import OrderedDict
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agents.orchestrator import build as build_orchestrator
from memory.context import RequestContext

app = BedrockAgentCoreApp()
log = app.logger

MAX_CACHED_AGENTS = 128

# Reuses one orchestrator per (actor, session) so a returning turn skips both the
# build and the history restore. The cache is bounded to 128 with LRU eviction so a
# single process serving many farmers cannot grow without limit.
#
# The key includes the actor, not just the session: the session id arrives from the
# client while the actor is derived from a verified token, so keying on the session
# alone would let a crafted session id collide onto another farmer's cached agent —
# and that agent holds their conversation.
#
# Eviction is now cheap. Conversation state lives in AgentCore Memory, so dropping a
# cached agent costs a rebuild and a restore, not the conversation. Before the
# session manager, eviction silently erased it.
_cache: "OrderedDict[tuple[str, str], Any]" = OrderedDict()
# One build at a time. Two turns arriving together for a cold session would
# otherwise both build an agent, both restore the same history, and one would be
# thrown away after having already written to memory.
_build_lock = asyncio.Lock()


async def get_or_create_agent(context: RequestContext):
    key = (context.actor_id, context.session_id)
    async with _build_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        if len(_cache) >= MAX_CACHED_AGENTS:
            _cache.popitem(last=False)
        # Constructing the agent reads the session back from AgentCore Memory over
        # blocking boto3 calls, and Strands forbids an async initialization hook, so
        # the build goes to a worker thread rather than stalling the event loop that
        # is streaming to the farmer.
        agent = await asyncio.to_thread(build_orchestrator, context)
        _cache[key] = agent
        return agent


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise ValueError("each message content value must be a list of content blocks")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError("tool_results must contain objects with a toolUseId string")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    session_id = getattr(context, 'session_id', 'default-session')
    # Identity and profile come from the payload the chat Lambda built out of the
    # verified Cognito claims, never from anything the browser chose. See
    # memory/context.py for why that distinction is load-bearing.
    request = RequestContext.from_payload(payload, session_id)
    agent = await get_or_create_agent(request)

    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(
        prompt,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
