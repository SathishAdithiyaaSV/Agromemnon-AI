"""Holds uploaded photos for the length of a turn, addressed by a short reference.

Why a store instead of passing the image through the conversation: the orchestrator
reaches its specialists through `Agent.as_tool()`, and a tool call carries a JSON
string. There is nowhere in that boundary to put a megabyte of JPEG. Base64 in the
tool arguments is worse than it sounds — the orchestrator's model would have to
*emit* the entire image token by token to call the tool, which costs more than the
diagnosis and truncates long before it finishes.

So the bytes never enter the model's context. main.py decodes the upload, puts it
here, and tells the orchestrator only a reference like `img_7f3a2b1c`. Whichever
agent or tool needs the pixels resolves the reference and reads them directly.

The store is process-local and bounded. A reference is valid on the AgentCore
worker that received the upload, for as long as it survives eviction — which covers
the turn it was uploaded in, and usually the few turns after. Nothing durable is
promised: a reference that has expired reads as "the photo is no longer available",
and the agent asks the farmer to send it again.
"""

import base64
import binascii
import hashlib
import re
import threading
import time
from collections import OrderedDict

# Bedrock's Converse API accepts these four; anything else has to be rejected here
# because the image content block names the format and the service validates it.
SUPPORTED_FORMATS = ("jpeg", "png", "gif", "webp")

# Roughly 5 MB of decoded image. Claude downsamples anything larger anyway, and the
# request has to cross API Gateway's 10 MB ceiling as base64 before it reaches us.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

MAX_ENTRIES = 64
TTL_SECONDS = 30 * 60

DATA_URL = re.compile(r"^data:(?P<mime>image/[A-Za-z0-9.+-]+)\s*;\s*base64\s*,", re.IGNORECASE)
REFERENCE = re.compile(r"img_[0-9a-f]{12}")

# Magic bytes, checked against the declared MIME type. A browser will happily label
# a HEIC photo image/jpeg; sending that to Bedrock fails with an opaque validation
# error, and catching it here produces a message the farmer can act on.
SIGNATURES = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


class ImageTooLarge(ValueError):
    """The upload exceeds MAX_IMAGE_BYTES once decoded."""


class UnsupportedImage(ValueError):
    """The upload is not a data URL in a format Bedrock accepts."""


_lock = threading.Lock()
_entries: "OrderedDict[str, tuple[float, bytes, str]]" = OrderedDict()


def _sniff_format(raw: bytes) -> str | None:
    for signature, name in SIGNATURES:
        if raw.startswith(signature):
            return name
    # WebP is RIFF....WEBP — the length field sits between the two markers.
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _purge(now: float) -> None:
    """Drop expired entries. Caller holds the lock."""
    for reference in [ref for ref, (stored_at, _, _) in _entries.items() if now - stored_at > TTL_SECONDS]:
        _entries.pop(reference, None)


def decode_data_url(data_url: str) -> tuple[bytes, str]:
    """Turn a `data:image/jpeg;base64,...` string into (bytes, bedrock format name)."""
    if not isinstance(data_url, str) or not data_url:
        raise UnsupportedImage("image must be a non-empty data URL string")

    match = DATA_URL.match(data_url)
    if not match:
        raise UnsupportedImage("image must be a data URL, e.g. data:image/jpeg;base64,...")

    # Reject on the encoded length before decoding, so an oversized upload cannot
    # cost us the memory of materialising it first.
    encoded = data_url[match.end():]
    if len(encoded) > MAX_IMAGE_BYTES * 4 // 3 + 4:
        raise ImageTooLarge(f"image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise UnsupportedImage("image data is not valid base64") from error

    if not raw:
        raise UnsupportedImage("image data is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageTooLarge(f"image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    # The sniffed format wins over the declared MIME type, which is client-supplied.
    image_format = _sniff_format(raw)
    if image_format is None:
        declared = match.group("mime").lower().removeprefix("image/")
        declared = "jpeg" if declared == "jpg" else declared
        raise UnsupportedImage(
            f"unrecognised image data (declared {declared!r}); send a JPEG, PNG, GIF or WebP"
        )
    if image_format not in SUPPORTED_FORMATS:
        raise UnsupportedImage(f"{image_format} images are not supported; send a JPEG or PNG")

    return raw, image_format


def put(raw: bytes, image_format: str) -> str:
    """Store bytes and return the reference the agent will pass around.

    The reference is derived from the content, so re-uploading the same photo in a
    later turn resolves to the one entry instead of filling the store with copies.
    """
    reference = "img_" + hashlib.sha256(raw).hexdigest()[:12]
    now = time.time()

    with _lock:
        _purge(now)
        _entries[reference] = (now, raw, image_format)
        _entries.move_to_end(reference)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)

    return reference


def store_data_url(data_url: str) -> str:
    """Decode a data URL and store it. Raises UnsupportedImage / ImageTooLarge."""
    raw, image_format = decode_data_url(data_url)
    return put(raw, image_format)


def get(reference: str) -> tuple[bytes, str] | None:
    """Resolve a reference to (bytes, format), or None if unknown or expired."""
    if not isinstance(reference, str):
        return None

    # Models routinely wrap the reference in backticks, quotes or a sentence.
    # Pulling the token out is cheaper than teaching four prompts to be exact.
    found = REFERENCE.search(reference)
    if not found:
        return None

    now = time.time()
    with _lock:
        _purge(now)
        entry = _entries.get(found.group(0))
        if entry is None:
            return None
        _entries.move_to_end(found.group(0))
        _, raw, image_format = entry

    return raw, image_format
