"""Image inspection and vision-model analysis.

The module has two halves, and the split is the important part.

**Deterministic, always available.** :func:`probe` reads the image header and
reports format and pixel dimensions. It is pure stdlib byte parsing - no
Pillow, no model, no network - so a caller can always find out whether it was
handed a 200x150 thumbnail or a 6000x4000 scan before deciding what to do
with it. A tool that reasons about a drawing without knowing it received a
thumbnail will produce confident nonsense.

**Model-backed, conditional.** :func:`analyse` sends the image to the model
configured for the ``vision`` role. If no vision model is configured, or the
provider cannot accept images, it raises :class:`ToolUnavailable` naming the
setting to change. It does not fall back to a text-only model and describe an
image it never saw, which is the failure mode this file exists to prevent.
"""

from __future__ import annotations

import base64
import struct
from typing import Any

from backend.tools.base import ToolArgumentError, ToolContext, ToolError, ToolUnavailable

#: Ceiling on an inbound image. Vision models degrade well before this; the
#: limit exists to stop a 100 MB TIFF being base64-encoded into memory.
MAX_IMAGE_BYTES = 12 * 1024 * 1024

#: Below this, a photo of a nameplate or a drawing region is not legible and
#: an answer from it should not be trusted.
MIN_USEFUL_PIXELS = 200

MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "tiff": "image/tiff",
}

_NO_VISION_MODEL = (
    "image analysis is unavailable: no model is configured for the 'vision' "
    "role. Set P117_VISION_MODEL to a locally served multimodal tag (see "
    ".env.example) and confirm it appears in GET /api/models."
)

_NO_ROUTER = (
    "image analysis is unavailable: no model router was supplied to this tool "
    "call, so no vision model can be resolved."
)

_NO_IMAGE_SUPPORT = (
    "image analysis is unavailable: the configured model provider does not "
    "accept image inputs. A text-only provider cannot be used here - it would "
    "describe an image it never received."
)


def _u32be(data: bytes, offset: int) -> int:
    return struct.unpack(">I", data[offset : offset + 4])[0]


def _u16le(data: bytes, offset: int) -> int:
    return struct.unpack("<H", data[offset : offset + 2])[0]


def _i32le(data: bytes, offset: int) -> int:
    return struct.unpack("<i", data[offset : offset + 4])[0]


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    return _u32be(data, 16), _u32be(data, 20)


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    # Walk the marker segments looking for a start-of-frame.
    index = 2
    length = len(data)
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment_length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        if marker in sof_markers:
            height = struct.unpack(">H", data[index + 5 : index + 7])[0]
            width = struct.unpack(">H", data[index + 7 : index + 9])[0]
            return width, height
        index += 2 + segment_length
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        # Frame header: 3-byte tag, 3-byte sync code, then 16-bit dimensions.
        width = _u16le(data, 26) & 0x3FFF
        height = _u16le(data, 28) & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None


def probe(data: bytes) -> dict[str, Any]:
    """Report format and dimensions from the image header alone.

    Raises :class:`ToolArgumentError` when the bytes are not a recognised
    image, rather than returning a shrug that a caller might treat as success.
    """
    if not data:
        raise ToolArgumentError("no image bytes were supplied")
    if len(data) > MAX_IMAGE_BYTES:
        raise ToolArgumentError(f"image is {len(data)} bytes; the limit is {MAX_IMAGE_BYTES}")

    fmt: str | None = None
    size: tuple[int, int] | None = None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        fmt, size = "png", _png_size(data)
    elif data.startswith(b"\xff\xd8"):
        fmt, size = "jpeg", _jpeg_size(data)
    elif data.startswith((b"GIF87a", b"GIF89a")):
        fmt, size = "gif", (_u16le(data, 6), _u16le(data, 8))
    elif data.startswith(b"BM") and len(data) >= 26:
        fmt, size = "bmp", (abs(_i32le(data, 18)), abs(_i32le(data, 22)))
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        fmt, size = "webp", _webp_size(data)
    elif data.startswith((b"II*\x00", b"MM\x00*")):
        # TIFF dimensions live in the IFD, which needs a real parser. The
        # format is identified; the size is reported as unknown rather than
        # guessed.
        fmt, size = "tiff", None

    if fmt is None:
        raise ToolArgumentError(
            "the supplied bytes are not a recognised image (png, jpeg, gif, bmp, webp, tiff)"
        )

    width, height = size if size else (None, None)
    legible = None
    if width and height:
        legible = min(width, height) >= MIN_USEFUL_PIXELS
    return {
        "format": fmt,
        "mime_type": MIME_BY_FORMAT[fmt],
        "width": width,
        "height": height,
        "size_bytes": len(data),
        "megapixels": round(width * height / 1_000_000, 3) if width and height else None,
        "likely_legible": legible,
        "note": (
            "dimensions are not read for TIFF; convert to PNG for a reliable probe"
            if fmt == "tiff"
            else (
                f"smallest side is under {MIN_USEFUL_PIXELS}px - text in this image "
                "may not be readable"
                if legible is False
                else ""
            )
        ),
    }


def to_data_url(data: bytes, *, mime_type: str | None = None) -> str:
    """Encode image bytes as a data URL for an OpenAI-style image part."""
    mime = mime_type or probe(data)["mime_type"]
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def decode_base64(value: str) -> bytes:
    """Accept a bare base64 string or a full data URL."""
    text = str(value or "").strip()
    if not text:
        raise ToolArgumentError("no image data was supplied")
    if text.startswith("data:"):
        _, _, remainder = text.partition(",")
        text = remainder
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ToolArgumentError(f"image data is not valid base64: {exc}") from exc


async def resolve_vision_model(context: ToolContext) -> Any:
    """Resolve the ``vision`` role, or explain precisely why it cannot be."""
    router = getattr(context, "router", None)
    if router is None:
        raise ToolUnavailable(_NO_ROUTER)
    from backend.models.providers.base import supports_images
    from backend.models.router.model_router import ModelUnavailableError

    try:
        resolved = await router.resolve("vision")
    except ModelUnavailableError as exc:
        raise ToolUnavailable(f"{_NO_VISION_MODEL} ({exc})") from exc
    if not supports_images(resolved.provider):
        raise ToolUnavailable(_NO_IMAGE_SUPPORT)
    return resolved


async def analyse(
    context: ToolContext,
    *,
    data: bytes,
    prompt: str,
    system: str | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = 1200,
) -> dict[str, Any]:
    """Ask the vision model about one image.

    The returned payload always carries ``image`` (the deterministic probe)
    and ``model``, so a reader can tell what was actually looked at and by
    what. An answer with no provenance is not usable as evidence.
    """
    if not str(prompt or "").strip():
        raise ToolArgumentError("a prompt describing what to look for is required")
    metadata = probe(data)
    resolved = await resolve_vision_model(context)

    from backend.models.providers.base import ProviderError

    try:
        result = await resolved.provider.chat_multimodal(
            model=resolved.model,
            prompt=str(prompt),
            images=[to_data_url(data, mime_type=metadata["mime_type"])],
            system=system,
            temperature=float(temperature),
            max_tokens=max_tokens,
        )
    except ProviderError as exc:
        raise ToolUnavailable(f"the vision model could not be reached: {exc}") from exc
    except Exception as exc:
        raise ToolError(f"vision analysis failed: {type(exc).__name__}: {exc}") from exc

    return {
        "text": result.content,
        "model": result.model,
        "provider": resolved.provider_name,
        "image": metadata,
        "usage": dict(result.usage or {}),
        "caveat": (
            metadata["note"]
            or "a vision model's reading of an image is an interpretation, not a measurement"
        ),
    }


__all__ = [
    "MAX_IMAGE_BYTES",
    "MIME_BY_FORMAT",
    "MIN_USEFUL_PIXELS",
    "analyse",
    "decode_base64",
    "probe",
    "resolve_vision_model",
    "to_data_url",
]
