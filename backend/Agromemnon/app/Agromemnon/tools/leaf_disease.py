"""Classify a tomato leaf photo with the SageMaker model trained on PlantVillage.

The endpoint is served by scripts/plantvillage/ — a MobileNetV3-Small fine-tuned on
the ten PlantVillage tomato classes. This tool resolves the image reference the
farmer's upload was stored under, sends the raw bytes to the endpoint, and returns
the top predictions together with the treatment record for the winning class.

Diagnosis and treatment come back in one call on purpose. If the agent had to make
a second call to look the cure up, a turn where that second call fails leaves it
holding a disease name and an urge to fill in the treatment from memory — which is
exactly what the shared no-invention guardrail exists to prevent.

The confidence thresholds below are advice to the model, not a filter. A low-
confidence result is still returned, flagged, because "the model is unsure, here
are the two it is choosing between" is a more useful answer to a farmer than
silence, provided the agent says so.
"""

import json
import logging
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from strands import tool

import image_store
from tools.leaf_disease_treatments import for_label

logger = logging.getLogger(__name__)

ENDPOINT_NAME = os.environ.get("LEAF_DISEASE_ENDPOINT", "agromemnon-leaf-disease")
REGION = os.environ.get("LEAF_DISEASE_REGION", "us-east-1")

# A serverless endpoint cold-starts in a few seconds. The read timeout has to clear
# that without eating the whole 30s the API gateway allows the turn.
READ_TIMEOUT_SECONDS = 20
CONNECT_TIMEOUT_SECONDS = 5

# Above CONFIDENT the top class can be stated plainly. Between the two, name it as
# the likeliest and give the runner-up. Below UNCERTAIN, treat the photo as
# unusable rather than guessing at a disease the farmer will then spray for.
CONFIDENT = 0.70
UNCERTAIN = 0.40

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "sagemaker-runtime",
            region_name=REGION,
            config=Config(
                read_timeout=READ_TIMEOUT_SECONDS,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # One retry covers a cold-start timeout; more would run the turn
                # past the gateway deadline with nothing to show for it.
                retries={"max_attempts": 1},
            ),
        )
    return _client


def _content_type(image_format: str) -> str:
    return "image/png" if image_format == "png" else "image/jpeg"


def _guidance(top_confidence: float, predictions: list[dict]) -> tuple[str, str]:
    """Return (certainty, instruction) telling the agent how far to trust this."""
    if top_confidence >= CONFIDENT:
        return "confident", (
            "State this diagnosis directly and give the treatment below."
        )
    if top_confidence >= UNCERTAIN:
        runner_up = predictions[1]["common_name"] if len(predictions) > 1 else "another disease"
        return "uncertain", (
            f"Say this is the most likely diagnosis but that you are not certain, and name "
            f"{runner_up} as the other possibility. Give the treatment for the top one and "
            f"suggest the farmer confirm with their KVK before spending on chemicals."
        )
    return "inconclusive", (
        "Do not name a disease. Tell the farmer the photo was not clear enough to "
        "identify and ask for another: a single affected leaf filling the frame, in "
        "daylight, with the underside shown too."
    )


@tool
def leaf_disease_classify(image_ref: str) -> dict:
    """Identify the disease in a photo of a tomato leaf and return how to treat it.

    Runs the trained tomato leaf disease classifier over the photo the farmer
    uploaded, and returns the likeliest diseases with a confidence score plus the
    cultural and chemical treatment for the top one.

    Args:
        image_ref: The photo reference from the farmer's message, like "img_7f3a2b1c".
    """
    resolved = image_store.get(image_ref)
    if resolved is None:
        return {
            "error": "no_image",
            "message": (
                "That photo is no longer available. Ask the farmer to attach the leaf "
                "photo again in their next message."
            ),
        }

    raw, image_format = resolved

    try:
        response = _get_client().invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType=_content_type(image_format),
            Accept="application/json",
            Body=raw,
        )
        body = json.loads(response["Body"].read())
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        logger.warning("leaf disease endpoint %s failed: %s", ENDPOINT_NAME, error)
        if code in ("ValidationError", "ResourceNotFound"):
            return {
                "error": "endpoint_unavailable",
                "message": (
                    "The leaf disease model is not reachable. Tell the farmer you could not "
                    "analyse the photo, and answer from what they described in words."
                ),
            }
        return {
            "error": "classification_failed",
            "message": "The leaf disease model could not be reached this time.",
        }
    except (BotoCoreError, json.JSONDecodeError, KeyError) as error:
        logger.warning("leaf disease endpoint returned an unreadable response: %s", error)
        return {
            "error": "classification_failed",
            "message": "The leaf disease model could not be reached this time.",
        }

    raw_predictions = body.get("predictions") or []
    if not raw_predictions:
        return {
            "error": "classification_failed",
            "message": "The leaf disease model returned no prediction for this photo.",
        }

    predictions = []
    for entry in raw_predictions:
        label = entry.get("label", "")
        record = for_label(label)
        predictions.append({
            "label": label,
            "common_name": record["common_name"] if record else label,
            "confidence": entry.get("confidence"),
        })

    top = predictions[0]
    top_confidence = top["confidence"] if isinstance(top["confidence"], (int, float)) else 0.0
    certainty, instruction = _guidance(top_confidence, predictions)

    result = {
        "crop": "tomato",
        "predictions": predictions,
        "certainty": certainty,
        "how_to_present": instruction,
        "model": {
            "source": "MobileNetV3-Small fine-tuned on the PlantVillage tomato subset",
            "endpoint": ENDPOINT_NAME,
            "scope": (
                "Trained on tomato only. It will force any leaf into one of ten tomato "
                "classes, so a photo of another crop produces a confident wrong answer."
            ),
        },
    }

    if certainty != "inconclusive":
        treatment = for_label(top["label"])
        if treatment:
            result["diagnosis"] = top["common_name"]
            result["treatment"] = treatment
        else:
            # A label with no treatment record means the deployed endpoint and this
            # file have drifted apart. Say so rather than answering half a question.
            logger.error("no treatment record for label %r", top["label"])
            result["treatment_unavailable"] = (
                f"No treatment reference is on file for {top['label']}. Give the farmer the "
                "identification only and tell them to confirm the treatment with their KVK."
            )

    return result
