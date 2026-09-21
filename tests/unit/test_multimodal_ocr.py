"""Unit tests for multimodal OCR and vision extraction pipeline."""

import io
from unittest.mock import MagicMock, patch

from backend.ingestion.ocr.extractor import OCRExtractor
from backend.tools.vision.ocr import extract_identifiers
from PIL import Image, ImageDraw


def _create_test_image(text: str = "TEST-TAG C-3") -> bytes:
    img = Image.new("RGB", (200, 60), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_extractor_is_image():
    extractor = OCRExtractor()
    assert extractor.is_image("document.png") is True
    assert extractor.is_image("photo.JPG") is True
    assert extractor.is_image("scan.TIFF") is True
    assert extractor.is_image("doc.pdf") is False
    assert extractor.is_image("table.csv") is False


def test_ocr_extractor_fallback_when_tesseract_missing():
    extractor = OCRExtractor()
    data = _create_test_image()

    with patch.dict("sys.modules", {"pytesseract": None}):
        result = extractor.extract_from_bytes(data)
        assert result.ok is True
        assert "Image: 200x60" in result.text
        assert result.metadata["engine"] == "metadata_fallback"


def test_ocr_extractor_success_with_engine():
    extractor = OCRExtractor()
    data = _create_test_image()

    mock_pytesseract = MagicMock()
    mock_pytesseract.image_to_string.return_value = "EQUIPMENT P-1042"

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        result = extractor.extract_from_bytes(data)
        assert result.ok is True
        assert result.text == "EQUIPMENT P-1042"
        assert result.confidence >= 0.9
        assert result.metadata["engine"] == "tesseract"


def test_extract_identifiers_regex():
    sample = (
        "Found pump P-1042 on line 6-P-1042-A1 during WO-8852 inspection. Temperature was 79 C."
    )
    found = extract_identifiers(sample)
    assert "P-1042" in found.get("equipment_tag", [])
    assert "WO-8852" in found.get("work_order", [])
    assert any("79" in m for m in found.get("measurement", []))
