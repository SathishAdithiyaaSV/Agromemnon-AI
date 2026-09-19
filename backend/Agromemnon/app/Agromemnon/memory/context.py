"""Who is asking, and which conversation this is.

AgentCore Memory is addressed by three ids: the memory resource, an *actor* and a
*session*. Cross-chat recall exists because the actor outlives the session — a fact
extracted from last month's conversation lands in the actor's namespace, which every
later conversation reads from. Get the actor id wrong and the farmer starts from
scratch each time; share it between farmers and one farmer reads another's memories.

So the actor id comes from the Cognito ID token that the API Gateway JWT authorizer
has already verified, and never from the request body. The body is client-controlled:
a caller who could name their own actor id could set it to someone else's `sub` and
retrieve their land size, their soil readings and their scheme applications. The
Lambda in infra/api.yaml reads the claim and forwards it; this module only trusts
what arrives in that field and degrades to an anonymous, session-scoped actor when
the endpoint is running unauthenticated.

The profile arrives the same way, from the same verified claims, which is why it can
be stated to the model as fact rather than as something the farmer asserted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

# Cognito custom attributes, minus the "custom:" prefix the Lambda strips.
_PROFILE_FIELDS = ("name", "state", "district", "language", "age")

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "mr": "Marathi",
    "ta": "Tamil",
}


def _clean(value: Any) -> str | None:
    """Return a non-empty trimmed string, or None for anything else."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True)
class FarmerProfile:
    """The farmer's standing details, as verified Cognito claims.

    Only the fields the agent actually reasons with are carried. Email is
    deliberately absent: it identifies the farmer without helping any tool, and
    dropping it here keeps it out of prompts, out of memory events and out of logs.
    """

    name: str | None = None
    state: str | None = None
    district: str | None = None
    language: str | None = None
    age: int | None = None

    @classmethod
    def from_mapping(cls, raw: Any) -> "FarmerProfile":
        if not isinstance(raw, Mapping):
            return cls()
        values: dict[str, Any] = {field: _clean(raw.get(field)) for field in _PROFILE_FIELDS}
        # Age arrives as a string in a JWT claim and is optional everywhere.
        age = values.pop("age")
        try:
            parsed = int(age) if age is not None else None
        except ValueError:
            parsed = None
        values["age"] = parsed if parsed and 0 < parsed < 120 else None
        return cls(**values)

    @property
    def where(self) -> str | None:
        """The farmer's location, narrowest part first, as the tools expect it."""
        parts = [part for part in (self.district, self.state) if part]
        return ", ".join(parts) if parts else None

    def describe(self) -> str:
        """Render the profile as a system-prompt block, or "" when nothing is known.

        This goes in the system prompt rather than the first user message. The old
        approach prepended it to turn one, which meant the details survived only as
        long as the conversation history did — exactly what a cold start destroys.
        In the system prompt it is present on every turn by construction, including
        the turn after a restart.
        """
        facts = []
        if self.name:
            facts.append(f"Their name is {self.name}.")
        if self.where:
            facts.append(
                f"They farm in {self.where}, India. Use this location for weather, soil, "
                "fertilizer and mandi-price lookups unless the farmer names another place."
            )
        if self.language and self.language in LANGUAGE_NAMES and self.language != "en":
            facts.append(
                f"Their preferred language is {LANGUAGE_NAMES[self.language]}; answer in the "
                "language they actually wrote in, and fall back to this one if that is unclear."
            )
        if not facts:
            return ""

        return (
            "WHO YOU ARE TALKING TO.\n\n"
            + " ".join(facts)
            + "\n\nThese details come from the farmer's own signed-in account, so treat them as "
            "established rather than asking them to confirm any of it. They are not a data "
            "source: a location tells you where to look something up, never what the answer is."
        )


@dataclass(frozen=True)
class RequestContext:
    """The identity and standing details behind one invocation."""

    actor_id: str
    session_id: str
    profile: FarmerProfile

    @classmethod
    def from_payload(cls, payload: Any, session_id: str) -> "RequestContext":
        """Build the context from the runtime payload and the runtime session id.

        `actorId` is set by the chat Lambda from the verified `sub` claim. When the
        API is deployed with auth switched off there is no claim to read, so the
        actor falls back to a hash of the session id: memory still works within the
        conversation, and no two anonymous callers can collide onto one actor.
        """
        raw = payload if isinstance(payload, Mapping) else {}
        actor_id = _clean(raw.get("actorId"))
        if actor_id is None:
            actor_id = "anon-" + hashlib.sha256(session_id.encode()).hexdigest()[:24]
        return cls(
            actor_id=actor_id,
            session_id=session_id,
            profile=FarmerProfile.from_mapping(raw.get("profile")),
        )
