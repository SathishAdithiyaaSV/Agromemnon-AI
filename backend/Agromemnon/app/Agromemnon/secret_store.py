"""Resolves an API key from the environment, or from Secrets Manager.

Three keys now follow the same rule — Gemini, WeatherAPI and data.gov.in — so the rule
lives here rather than in three copies that drift apart. Each key is read from one of
two places:

`<NAME>` directly, which is how local development works: `agentcore/.env.local` is
gitignored, so a key there is a key that stays on the machine.

`<NAME>_SECRET` otherwise, naming a Secrets Manager secret read once at startup. An
AgentCore runtime's environment variables are plain text in the deployed config, and
`agentcore.json` is committed, so a key put there is a key published to whoever can read
the repository. The runtime's execution role is what grants access instead — see
policies/gemini-api-key.json and policies/external-api-keys.json.

The variable holds a secret *name*, not an ARN, because GetSecretValue accepts either and
a name needs no account id — so the committed config carries no placeholder ARN that must
be edited before the first deploy.

Resolution never raises. A key that cannot be found returns None and the caller decides
what that costs: the model falls back to another provider, a tool tells the farmer which
answer it could not fetch. A runtime that refuses to start because one of three optional
keys is missing fails every question, including the ones that key had nothing to do with.
"""

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def resolve(name: str) -> str | None:
    """The value of key `name`, from `$<name>` or the secret named by `$<name>_SECRET`.

    Cached per name: the lookup is a network call, and the key does not change under a
    running process. Rotating a key takes a new runtime version, which is the same
    restart any environment variable change would need.
    """
    direct = (os.environ.get(name) or "").strip()
    if direct:
        return direct

    secret_id = (os.environ.get(f"{name}_SECRET") or "").strip()
    if not secret_id:
        return None

    try:
        return _read(secret_id, name)
    except Exception:
        # Reaching Secrets Manager is a network call against a resource this runtime may
        # not have been granted. Log it and let the caller degrade.
        logger.warning("Could not read %s from secret %s.", name, secret_id, exc_info=True)
        return None


def _read(secret_id: str, name: str) -> str | None:
    import boto3

    region = os.environ.get(f"{name}_SECRET_REGION") or os.environ.get("AWS_REGION")
    secret = boto3.client("secretsmanager", region_name=region).get_secret_value(
        SecretId=secret_id
    )["SecretString"]

    # Accept both a bare key and the {"<NAME>": "..."} shape the console produces when a
    # secret is created as key/value pairs rather than plaintext.
    try:
        parsed = json.loads(secret)
    except json.JSONDecodeError:
        return secret.strip() or None

    if isinstance(parsed, dict):
        for field in (name, "api_key", "apiKey"):
            value = parsed.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        logger.warning("Secret %s is JSON but holds no %s, api_key or apiKey field.", secret_id, name)
        return None

    return str(parsed).strip() or None
