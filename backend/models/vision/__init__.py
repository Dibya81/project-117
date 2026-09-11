"""Vision model role.

Optional. When it is unset, the vision *tools* still work in their
deterministic mode (stdlib image header probing) and raise ``ToolUnavailable``
naming ``P117_VISION_MODEL`` for anything that would need a model to look at
the picture. They never fall back to a text-only model — that would turn "I
cannot see this" into a confident invention.
"""

from backend.models.gateway.model_registry import RoleDescriptor

DESCRIPTOR = RoleDescriptor(
    role="vision",
    purpose=(
        "Reading images: equipment photographs, nameplates, gauge faces, "
        "scanned P&ID sheets and other engineering drawings."
    ),
    setting="P117_VISION_MODEL",
    modalities=("text", "image"),
    capabilities=("image_qa", "ocr", "drawing_analysis"),
    suggested_models=(
        "qwen2.5vl:7b",
        "llava:13b",
        "minicpm-v:8b",
    ),
    required_for_demo=False,
    notes=(
        "Requires a provider that can transmit images (see "
        "MultimodalProvider.supports_images). OCR through a vision model is an "
        "interpretation, not a verbatim transcription, and is labelled as such "
        "in tool output."
    ),
)

DESCRIPTORS = (DESCRIPTOR,)

__all__ = ["DESCRIPTOR", "DESCRIPTORS"]
