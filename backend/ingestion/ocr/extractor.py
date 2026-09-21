"""Multimodal OCR and image text extraction engine.

Provides sovereign offline OCR with graceful degradation when native OCR binaries
are absent.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error: str | None = None


class OCRExtractor:
    """Extracts text from images using available offline engines."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

    def __init__(self, languages: str = "eng", psm: int = 3) -> None:
        self.languages = languages
        self.psm = psm

    def is_image(self, file_path: Path | str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def extract_from_file(self, file_path: Path | str) -> OCRResult:
        path = Path(file_path)
        if not path.exists():
            return OCRResult(text="", confidence=0.0, ok=False, error=f"File not found: {path}")

        try:
            from PIL import Image

            img = Image.open(path)
            return self.extract_from_image(img)
        except Exception as exc:
            logger.warning("Failed to open image %s: %s", path, exc)
            return OCRResult(text="", confidence=0.0, ok=False, error=str(exc))

    def extract_from_bytes(self, data: bytes) -> OCRResult:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            return self.extract_from_image(img)
        except Exception as exc:
            logger.warning("Failed to process image bytes: %s", exc)
            return OCRResult(text="", confidence=0.0, ok=False, error=str(exc))

    def extract_from_image(self, image: Any) -> OCRResult:
        width, height = getattr(image, "size", (0, 0))
        img_format = getattr(image, "format", "UNKNOWN")
        meta = {
            "width": width,
            "height": height,
            "format": img_format,
            "engine": "none",
        }

        # Strategy 1: Pytesseract if installed and tesseract executable is found
        try:
            import pytesseract

            # Test if tesseract is accessible
            text = pytesseract.image_to_string(
                image,
                lang=self.languages,
                config=f"--psm {self.psm}",
            )
            meta["engine"] = "tesseract"
            return OCRResult(
                text=text.strip(),
                confidence=0.9 if text.strip() else 0.0,
                metadata=meta,
                ok=True,
            )
        except Exception as exc:
            logger.debug("Tesseract OCR not available: %s", exc)

        # Strategy 2: Fallback structured text inspection / image metadata extraction
        meta["engine"] = "metadata_fallback"
        fallback_text = f"[Image: {width}x{height} {img_format}]"
        return OCRResult(
            text=fallback_text,
            confidence=0.5,
            metadata=meta,
            ok=True,
            error="tesseract_unavailable",
        )
