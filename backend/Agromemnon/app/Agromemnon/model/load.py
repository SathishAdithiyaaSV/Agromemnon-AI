import os

from strands.models.gemini import GeminiModel


def load_model() -> GeminiModel:
    return GeminiModel(
        model_id="gemini-2.5-flash",
        client_args={
            "api_key": os.environ["GEMINI_API_KEY"]
        }
    )
