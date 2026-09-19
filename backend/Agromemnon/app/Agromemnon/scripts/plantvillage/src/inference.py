"""SageMaker serving handlers for the tomato leaf disease classifier.

Loaded by the PyTorch inference container, which calls model_fn once per worker
and then input_fn -> predict_fn -> output_fn per request.

The endpoint accepts raw image bytes (image/jpeg, image/png) because that is what
the caller in tools/leaf_disease.py already holds, and JSON with a base64 field as
a convenience for `aws sagemaker-runtime invoke-endpoint` from a shell.
"""

import base64
import io
import json
import logging
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

logger = logging.getLogger(__name__)

IMAGE_SIZE = 224
# Must match train.py exactly. Different normalisation at serving time shifts every
# activation and produces confident nonsense rather than an obvious failure.
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

TOP_K = 3

_transform = transforms.Compose([
    transforms.Resize(int(IMAGE_SIZE * 1.14)),
    transforms.CenterCrop(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


def model_fn(model_dir, context=None):
    directory = Path(model_dir)
    classes = json.loads((directory / "classes.json").read_text())

    network = models.mobilenet_v3_small(weights=None)
    network.classifier[-1] = nn.Linear(network.classifier[-1].in_features, len(classes))
    network.load_state_dict(torch.load(directory / "model.pth", map_location="cpu"))
    network.eval()

    logger.info("loaded classifier with %d classes", len(classes))
    return {"network": network, "classes": classes}


def input_fn(request_body, content_type="application/x-image", context=None):
    if content_type in ("application/x-image", "image/jpeg", "image/png", "application/octet-stream"):
        raw = request_body
    elif content_type == "application/json":
        payload = json.loads(request_body)
        encoded = payload.get("image_base64") or payload.get("image")
        if not encoded:
            raise ValueError("JSON body must carry an 'image_base64' field")
        raw = base64.b64decode(encoded)
    else:
        raise ValueError(f"unsupported content type {content_type!r}")

    if isinstance(raw, str):
        raw = raw.encode("latin-1")

    # convert("RGB") is not optional: phone photos arrive as RGBA or greyscale often
    # enough, and a 4- or 1-channel tensor fails inside the first convolution.
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return _transform(image).unsqueeze(0)


def predict_fn(tensor, model, context=None):
    network, classes = model["network"], model["classes"]

    with torch.no_grad():
        probabilities = torch.softmax(network(tensor), dim=1)[0]

    k = min(TOP_K, len(classes))
    scores, indices = torch.topk(probabilities, k)

    return {
        "predictions": [
            {"label": classes[index], "confidence": round(float(score), 4)}
            for score, index in zip(scores.tolist(), indices.tolist())
        ]
    }


def output_fn(prediction, accept="application/json", context=None):
    return json.dumps(prediction), "application/json"
