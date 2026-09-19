"""Loads the model every agent shares.

Bedrock is the primary and Gemini is the fallback, wired together with Strands'
`ModelRouter`. The router asks its strategy for a candidate before the first call
and again after any failed one, so a Bedrock throttle, outage or model error moves
the turn onto Gemini mid-conversation instead of losing it. `FallbackStrategy` is
ordered failover until a candidate starts failing repeatedly, after which the
healthier one is preferred and a success re-arms both.

Bedrock leads because the rest of the system already lives in this account: the
call is IAM-authorized by the runtime's execution role rather than a shared API
key, the farmer's question never leaves AWS, and it is billed with everything
else. Gemini stays because a single-provider agent is down when that provider is.

**Why Nova and not Claude.** Claude on Bedrock needs the Anthropic use-case
details form submitted for the account, and account 222758971755 has not
submitted it — every `us.anthropic.*` id returns ResourceNotFoundException
("Model use case details have not been submitted"). Nova needs no form and is
invocable today. Once the form is approved, switching is a `TEXT_MODEL_ID`
change on the runtime plus the matching resource in
policies/bedrock-text-model.json — no code change.

The Gemini key is resolved once per process, from one of two places:

`GEMINI_API_KEY` directly, which is how local development works.

`GEMINI_API_KEY_SECRET` otherwise, read from Secrets Manager at startup. An
AgentCore runtime's environment variables are plain text in the deployed config,
so a key put there is a key committed to the repository that produced it. Secrets
Manager keeps it out of git, and the runtime's execution role is what grants
access — see policies/gemini-api-key.json.

The variable holds a secret *name*, not an ARN, because GetSecretValue accepts
either and a name needs no account id. That keeps the deploy config free of a
placeholder ARN that has to be edited before the first deploy — the kind of step
that is discovered when the runtime fails on demand day. An ARN still works if
you prefer it.

A missing or unreadable Gemini key is no longer fatal. It once was: this module
read `os.environ["GEMINI_API_KEY"]` at import time while the deploy config never
set it, so a deployed container raised KeyError on its first import and the
runtime failed before any farmer question reached it. Now that Gemini is the
fallback rather than the only model, losing it costs redundancy, not the answer —
so the key is resolved defensively and its absence is logged and carried on from,
matching how every other AWS-backed capability here degrades.
"""

import json
import logging
import os
from functools import lru_cache

from strands.models.bedrock import BedrockModel
from strands.models.gemini import GeminiModel
from strands.models.routing import ModelRouter, RoutingCandidate

logger = logging.getLogger(__name__)

# Nova Pro rather than Nova Lite: the orchestrator's whole job is choosing which
# specialists a question belongs to and calling several of them in one turn, and
# the lighter model picks a single specialist for questions that span two.
TEXT_MODEL_ID = os.environ.get("TEXT_MODEL_ID", "us.amazon.nova-pro-v1:0")
TEXT_MODEL_REGION = (
    os.environ.get("TEXT_MODEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
)
GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.1-flash-lite")


@lru_cache(maxsize=1)
def _api_key() -> str | None:
    """The Gemini key, or None when this deployment has not been given one."""
    direct = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if direct:
        return direct

    secret_id = (os.environ.get("GEMINI_API_KEY_SECRET") or "").strip()
    if not secret_id:
        logger.warning(
            "No Gemini credentials; running on %s with no fallback. Set GEMINI_API_KEY "
            "for local runs, or GEMINI_API_KEY_SECRET to a Secrets Manager secret name "
            "for a deployed runtime.",
            TEXT_MODEL_ID,
        )
        return None

    try:
        return _read_secret(secret_id)
    except Exception:
        # Reaching Secrets Manager is a network call against a resource the runtime
        # may not have been granted. It must not take down a runtime whose primary
        # model is fine.
        logger.warning(
            "Could not read Gemini key from secret %s; running on %s with no fallback.",
            secret_id,
            TEXT_MODEL_ID,
            exc_info=True,
        )
        return None


def _read_secret(secret_id: str) -> str | None:
    import boto3

    region = os.environ.get("GEMINI_API_KEY_SECRET_REGION") or os.environ.get("AWS_REGION")
    client = boto3.client("secretsmanager", region_name=region)
    secret = client.get_secret_value(SecretId=secret_id)["SecretString"]

    # Accept both a bare key and the {"GEMINI_API_KEY": "..."} shape the console
    # produces when a secret is created as key/value pairs rather than plaintext.
    try:
        parsed = json.loads(secret)
    except json.JSONDecodeError:
        return secret.strip() or None
    if isinstance(parsed, dict):
        for field in ("GEMINI_API_KEY", "api_key", "apiKey"):
            value = parsed.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        logger.warning(
            "Secret %s is JSON but holds no GEMINI_API_KEY, api_key or apiKey field.",
            secret_id,
        )
        return None
    return str(parsed).strip() or None


def load_model():
    """The text model for the orchestrator and every specialist.

    Returns a `ModelRouter` running Bedrock with Gemini behind it, or the bare
    Bedrock model when no Gemini key is available — a router of one candidate
    would only add a failover that cannot fire.

    Each call builds fresh model objects. The router tracks per-candidate health
    and refuses to route to one model instance twice, so conversations must not
    share instances; a router is, however, safe to share across the agents built
    for one conversation, which is what the orchestrator does.
    """
    bedrock = BedrockModel(model_id=TEXT_MODEL_ID, region_name=TEXT_MODEL_REGION)

    api_key = _api_key()
    if api_key is None:
        return bedrock

    gemini = GeminiModel(model_id=GEMINI_MODEL_ID, client_args={"api_key": api_key})
    # Named so the routing logs say which provider a turn switched to, rather than
    # printing a model id the on-call reader has to recognise.
    return ModelRouter(
        [
            RoutingCandidate(model=bedrock, name="bedrock"),
            RoutingCandidate(model=gemini, name="gemini"),
        ]
    )


# Vision runs on Bedrock only. Nova Pro reads images, and the alternative was
# Claude Sonnet, which this account cannot invoke until the Anthropic use-case
# form is submitted — a vision agent pointed at a model that returns
# ResourceNotFoundException is a plant_doctor that never answers.
#
# There is deliberately no Gemini fallback here. The photo is the farmer's own
# field, and keeping it inside AWS — runtime to Bedrock, same account — is worth
# more than a second chance at answering.
VISION_MODEL_ID = os.environ.get("VISION_MODEL_ID", "us.amazon.nova-pro-v1:0")
VISION_MODEL_REGION = os.environ.get("VISION_MODEL_REGION", "us-east-1")


def load_vision_model() -> BedrockModel:
    """The model for the agents that have to look at a photograph.

    Separate from load_model() because the two jobs have different requirements.
    Reading a leaf photograph, weighing it against a classifier's confidence score
    and deciding whether the two agree is the one judgement call in this system
    where a weaker model produces a confidently wrong diagnosis a farmer then
    sprays for.
    """
    return BedrockModel(
        model_id=VISION_MODEL_ID,
        region_name=VISION_MODEL_REGION,
        # The diagnosis plus treatment runs long in Hindi or Kannada, where the
        # script costs more tokens per word than English.
        max_tokens=2048,
    )
