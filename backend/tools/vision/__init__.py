"""Vision helpers for tools.

:mod:`image_analysis` owns the deterministic probe and the single path to the
vision model; :mod:`ocr` transcribes text and says plainly that a language
model is not an OCR engine; :mod:`drawing_analysis` extracts structure from
engineering drawings and separates what was verified from what was merely
reported.
"""

from __future__ import annotations

from backend.tools.vision.drawing_analysis import (
    DRAWING_PROMPT,
    analyse_drawing,
    parse_response,
    verify_tags,
)
from backend.tools.vision.image_analysis import (
    MAX_IMAGE_BYTES,
    MIN_USEFUL_PIXELS,
    analyse,
    decode_base64,
    probe,
    resolve_vision_model,
    to_data_url,
)
from backend.tools.vision.ocr import (
    PATTERNS,
    extract_identifiers,
    extract_text,
)

__all__ = [
    "DRAWING_PROMPT",
    "MAX_IMAGE_BYTES",
    "MIN_USEFUL_PIXELS",
    "PATTERNS",
    "analyse",
    "analyse_drawing",
    "decode_base64",
    "extract_identifiers",
    "extract_text",
    "parse_response",
    "probe",
    "resolve_vision_model",
    "to_data_url",
    "verify_tags",
]
