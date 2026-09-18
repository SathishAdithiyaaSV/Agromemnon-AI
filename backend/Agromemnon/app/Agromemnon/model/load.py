import os

from google.genai import types
from strands.models.gemini import GeminiModel


def load_model() -> GeminiModel:
    return GeminiModel(
        # This lightweight model supports tool use and is currently available
        # to this project's Gemini API key. Override with GEMINI_MODEL when
        # another model has capacity for the key.
        model_id=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        client_args={
            "api_key": os.environ["GEMINI_API_KEY"],
            # The Google SDK does not retry unless retry_options are set. Retry
            # temporary capacity and transport failures before failing the turn.
            "http_options": types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=5,
                    initial_delay=1.0,
                    max_delay=8.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                )
            ),
        },
    )
