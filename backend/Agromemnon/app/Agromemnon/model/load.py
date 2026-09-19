"""Loads the model every agent shares.

The key is resolved once per process, from one of two places:

`GEMINI_API_KEY` directly, which is how local development works.

`GEMINI_API_KEY_SECRET` otherwise, read from Secrets Manager at startup. An AgentCore
runtime's environment variables are plain text in the deployed config, so a key put
there is a key committed to the repository that produced it. Secrets Manager keeps it
out of git, and the runtime's execution role is what grants access — see
policies/gemini-api-key.json.

The variable holds a secret *name*, not an ARN, because GetSecretValue accepts either
and a name needs no account id. That keeps the deploy config free of a placeholder
ARN that has to be edited before the first deploy — the kind of step that is
discovered when the runtime fails on demand day. An ARN still works if you prefer it.

This module used to read `os.environ["GEMINI_API_KEY"]` at import time while the
deploy config never set it, so a deployed container raised KeyError on its first
import and the runtime failed before any farmer question reached it. Hence the
explicit error below: the next person to hit this should be told what to set.
"""

import json
import os
from functools import lru_cache

from strands.models.gemini import GeminiModel

MODEL_ID = "gemini-3.6-flash"


@lru_cache(maxsize=1)
def _api_key() -> str:
    direct = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if direct:
        return direct

    secret_id = (os.environ.get("GEMINI_API_KEY_SECRET") or "").strip()
    if not secret_id:
        raise RuntimeError(
            "No Gemini credentials. Set GEMINI_API_KEY for local runs, or "
            "GEMINI_API_KEY_SECRET to a Secrets Manager secret name for a deployed runtime."
        )

    import boto3

    region = os.environ.get("GEMINI_API_KEY_SECRET_REGION") or os.environ.get("AWS_REGION")
    client = boto3.client("secretsmanager", region_name=region)
    secret = client.get_secret_value(SecretId=secret_id)["SecretString"]

    # Accept both a bare key and the {"GEMINI_API_KEY": "..."} shape the console
    # produces when a secret is created as key/value pairs rather than plaintext.
    try:
        parsed = json.loads(secret)
    except json.JSONDecodeError:
        return secret.strip()
    if isinstance(parsed, dict):
        for field in ("GEMINI_API_KEY", "api_key", "apiKey"):
            value = parsed.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise RuntimeError(
            f"Secret {secret_id} is JSON but holds no GEMINI_API_KEY, api_key or apiKey field."
        )
    return str(parsed).strip()


def load_model() -> GeminiModel:
    return GeminiModel(model_id=MODEL_ID, client_args={"api_key": _api_key()})
