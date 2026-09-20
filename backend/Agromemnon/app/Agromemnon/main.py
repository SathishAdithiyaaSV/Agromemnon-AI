import asyncio
from typing import Any
from collections import OrderedDict
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agents.orchestrator import build as build_orchestrator
from memory.context import RequestContext

import image_store

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


# What the orchestrator is told when a photo comes in. The bytes stay in
# image_store and only this reference reaches the model — see image_store for why.
PHOTO_NOTE = (
    "[The farmer attached a photo of their plant. Photo reference: {reference}. "
    "Pass this reference to plant_doctor exactly as written.]"
)


def _attach_image(payload: dict, prompt):
    """Store an attached photo and fold its reference into the prompt text.

    Only a plain string prompt is augmented. A caller supplying a full message
    history is driving the conversation itself and can place the reference where it
    wants it; quietly rewriting the tail of someone else's history would be worse
    than ignoring the field.
    """
    image = payload.get("image")
    if image is None:
        return prompt
    if not isinstance(prompt, str):
        log.warning("ignoring 'image' on a request that supplied its own message history")
        return prompt

    try:
        reference = image_store.store_data_url(image)
    except image_store.ImageTooLarge as error:
        log.warning("rejected oversized upload: %s", error)
        return (prompt + "\n\n[The farmer tried to attach a photo but it was too large to "
                         "read. Ask them to send a smaller one.]").strip()
    except image_store.UnsupportedImage as error:
        log.warning("rejected unreadable upload: %s", error)
        return (prompt + "\n\n[The farmer tried to attach a photo but it could not be read. "
                         "Ask them to send it again as a JPEG or PNG.]").strip()

    log.info("stored uploaded photo as %s", reference)
    note = PHOTO_NOTE.format(reference=reference)
    return f"{prompt}\n\n{note}" if prompt else note


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


def _prompt_for(payload: dict):
    """The prompt the agent runs on, with any attached photo registered."""
    return _attach_image(payload, _extract_prompt(payload))


# Nova emits its routing deliberation as literal "<thinking>...</thinking>" text in the
# reply stream, so without this the farmer's answer opens with the model explaining which
# specialist it is about to call. guardrails.FORMAT also forbids it, but that is a prompt
# rule shaping a cooperative model — the same reason guardrails.py gives for putting
# anything that must not happen into code. This is that code.
OPEN_TAG = "<thinking>"
CLOSE_TAG = "</thinking>"


def _partial_tag_len(buffer: str, tag: str) -> int:
    """Length of the buffer's tail that could still grow into `tag`.

    A tag can be split across two deltas ("<thin" + "king>"), so a tail that is a proper
    prefix of the tag is held back rather than emitted; anything else would print half a
    tag and then swallow the rest.
    """
    for size in range(min(len(tag) - 1, len(buffer)), 0, -1):
        if tag.startswith(buffer[-size:]):
            return size
    return 0


class ThinkingFilter:
    """Removes <thinking> spans from a stream of text deltas.

    Stateful because the tags and the text between them arrive in arbitrary chunks. Feed
    every delta through `feed()` and call `flush()` once the stream ends, which releases a
    tail that turned out not to be the start of a tag after all.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False

    def feed(self, text: str) -> str:
        self._buffer += text
        out = []
        while True:
            if self._inside:
                end = self._buffer.find(CLOSE_TAG)
                if end == -1:
                    # Keep only what might be a partial closing tag; the rest is
                    # deliberation and is dropped.
                    self._buffer = self._buffer[len(self._buffer) - _partial_tag_len(self._buffer, CLOSE_TAG):]
                    break
                self._buffer = self._buffer[end + len(CLOSE_TAG):]
                self._inside = False
                continue

            start = self._buffer.find(OPEN_TAG)
            if start == -1:
                hold = _partial_tag_len(self._buffer, OPEN_TAG)
                if hold:
                    out.append(self._buffer[:-hold])
                    self._buffer = self._buffer[-hold:]
                else:
                    out.append(self._buffer)
                    self._buffer = ""
                break

            out.append(self._buffer[:start])
            self._buffer = self._buffer[start + len(OPEN_TAG):]
            self._inside = True
        return "".join(out)

    def flush(self) -> str:
        """Release a held-back tail that never became a tag."""
        if self._inside:
            return ""
        tail, self._buffer = self._buffer, ""
        return tail


def _delta_text(event: dict):
    """The text of a contentBlockDelta event, or None if it is some other event."""
    delta = (event.get("event") or {}).get("contentBlockDelta")
    if not isinstance(delta, dict):
        return None
    text = (delta.get("delta") or {}).get("text")
    return text if isinstance(text, str) else None


def _text_event(text: str) -> dict:
    return {"event": {"contentBlockDelta": {"delta": {"text": text}}}}


# ---------------------------------------------------------------- agent credits
#
# Which specialists answered a question is worth telling the farmer: "this came
# from the crop and the market adviser" is a claim they can weigh, where an
# unattributed paragraph is not. The orchestrator must not say it itself — its
# prompt forbids mentioning specialists, and a model asked to report its own
# routing will sometimes report routing that did not happen. So the roster is
# read off the stream, where a specialist appears only because it was really
# called.
#
# It travels to the browser as a marker appended to the answer text rather than
# as its own event, because the chat Lambda between here and the browser keeps
# only `contentBlockDelta.delta.text` and discards everything else, and that
# Lambda is inlined against a 4096-character cap it has already nearly reached
# (see infra/api.yaml). An HTML comment is invisible if anything ever renders the
# text without stripping it first; the web client strips it in lib/api.ts.
SPECIALISTS = frozenset(
    {"crop_agent", "operations_agent", "advice_agent", "plant_doctor", "video_tutor"}
)

AGENTS_MARKER = "\n\n<!--agents:{names}-->"


def _tool_name(event: dict):
    """The tool a contentBlockStart is opening, or None for any other event."""
    start = (event.get("event") or {}).get("contentBlockStart", {}).get("start")
    if not isinstance(start, dict):
        return None
    name = (start.get("toolUse") or {}).get("name")
    return name if isinstance(name, str) else None


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    session_id = getattr(context, 'session_id', 'default-session')
    # Identity and profile come from the payload the chat Lambda built out of the
    # verified Cognito claims, never from anything the browser chose. See
    # memory/context.py for why that distinction is load-bearing.
    request = RequestContext.from_payload(payload, session_id)
    agent = await get_or_create_agent(request)

    prompt = _prompt_for(payload)

    thinking = ThinkingFilter()
    # A list, not a set: the order the orchestrator reached for each specialist is
    # the order the farmer's question raised them, which is the order to credit
    # them in. Repeat calls are folded, so one specialist asked twice is named once.
    consulted: list[str] = []

    async for event in agent.stream_async(
        prompt,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue

        called = _tool_name(event)
        if called in SPECIALISTS and called not in consulted:
            consulted.append(called)

        text = _delta_text(event)
        if text is None:
            yield event
            continue
        # A delta that was entirely deliberation yields nothing rather than an empty
        # delta, which a consumer counting chunks would otherwise see as output.
        kept = thinking.feed(text)
        if kept:
            yield _text_event(kept)

    tail = thinking.flush()
    if tail:
        yield _text_event(tail)

    if consulted:
        yield _text_event(AGENTS_MARKER.format(names=",".join(consulted)))


if __name__ == "__main__":
    app.run()
