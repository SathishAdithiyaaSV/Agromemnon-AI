import os

from strands.models.gemini import GeminiModel


def load_model() -> GeminiModel:
    return GeminiModel(
        model_id="gemini-3.1-flash-lite",
        client_args={
            "api_key": os.environ["GEMINI_API_KEY"]
        }
    )