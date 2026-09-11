"""Reading text out of an image.

There is one honesty problem with OCR-by-vision-model and this module is built
around it: a multimodal LLM does not transcribe, it *predicts* text. It will
happily complete a partly legible tag number into something plausible. So:

* the prompt forbids guessing and requires ``[illegible]`` for anything the
  model cannot actually read;
* the result is labelled ``method: "vision_model"`` and ``verbatim: false``,
  because nothing downstream should treat it as a faithful transcription;
* :func:`extract_identifiers` re-scans the returned text with real regexes for
  the identifier shapes this domain uses (equipment tags, line numbers, work
  order ids), so a caller gets deterministically-found identifiers rather than
  the model's summary of them.

If a dedicated OCR engine is installed later, it belongs behind
:func:`extract_text` as a preferred backend - the contract here does not
assume a model.
"""

from __future__ import annotations

import re
from typing import Any

from backend.tools.base import ToolContext
from backend.tools.vision.image_analysis import analyse

OCR_SYSTEM = (
    "You transcribe text from industrial images: nameplates, gauges, labels, "
    "placards and drawing annotations."
)

OCR_PROMPT = (
    "Transcribe every piece of text visible in this image, preserving line "
    "breaks and reading order.\n"
    "Rules:\n"
    "- Do not guess. If a character or word is not clearly legible, write "
    "[illegible] in its place.\n"
    "- Do not correct, expand, normalise or reformat anything - copy exactly "
    "what is shown, including units and punctuation.\n"
    "- Do not describe the image, add commentary, or infer values that are not "
    "written.\n"
    "- If there is no text at all, reply with exactly: NO TEXT FOUND"
)

NO_TEXT_MARKER = "NO TEXT FOUND"

#: Identifier shapes used across the operations domain. Deterministic, so an
#: identifier either matches the documented pattern or is not claimed as one.
PATTERNS: dict[str, re.Pattern[str]] = {
    # Equipment tag: letter block, hyphen, number block (C-3, P-1042, V-2210).
    "equipment_tag": re.compile(r"\b[A-Z]{1,3}-\d{1,5}[A-Z]?\b"),
    # Work order: WO-8852.
    "work_order": re.compile(r"\bWO-\d{3,6}\b"),
    # Process line: 6"-P-1042-A1 style, tolerant of spacing.
    "line_number": re.compile(r"\b\d{1,2}\"?-[A-Z]{1,3}-\d{2,5}(?:-[A-Z0-9]{1,4})?\b"),
    # Serial / model strings on a nameplate.
    "serial": re.compile(r"\b(?:S/?N|SER(?:IAL)?)[:. ]*([A-Z0-9-]{4,20})\b", re.I),
    # A measurement with a unit, e.g. "6.8 mm/s" or "79 C".
    "measurement": re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:mm/s|mm|bar|kPa|MPa|psi|rpm|kW|A|V|Hz|C|F|%)\b"
    ),
}


def extract_identifiers(text: str) -> dict[str, list[str]]:
    """Find domain identifiers in transcribed text, deterministically.

    Order is preserved and duplicates removed, so the output is stable enough
    to compare between two runs.
    """
    body = str(text or "")
    found: dict[str, list[str]] = {}
    for label, pattern in PATTERNS.items():
        hits: list[str] = []
        for match in pattern.finditer(body):
            value = (match.group(1) if pattern.groups else match.group(0)).strip()
            if value and value not in hits:
                hits.append(value)
        if hits:
            found[label] = hits
    return found


def illegible_count(text: str) -> int:
    return str(text or "").lower().count("[illegible]")


async def extract_text(
    context: ToolContext,
    *,
    data: bytes,
    hint: str = "",
) -> dict[str, Any]:
    """Transcribe an image's text and report how trustworthy it is.

    ``hint`` is appended to the prompt for cases where the caller knows what
    it is looking at ("this is a compressor nameplate"). It cannot relax the
    no-guessing rules, which are fixed.
    """
    prompt = OCR_PROMPT
    if str(hint or "").strip():
        prompt = f"{OCR_PROMPT}\n\nContext for this image: {str(hint).strip()[:400]}"

    outcome = await analyse(
        context,
        data=data,
        prompt=prompt,
        system=OCR_SYSTEM,
        temperature=0.0,
        max_tokens=2000,
    )
    text = str(outcome.get("text") or "").strip()
    empty = text.upper().startswith(NO_TEXT_MARKER)
    if empty:
        text = ""
    unreadable = illegible_count(text)

    return {
        "text": text,
        "found_text": not empty,
        "identifiers": extract_identifiers(text),
        "illegible_markers": unreadable,
        "method": "vision_model",
        # Stated on every result, not just the doubtful ones: a language model
        # predicting characters is not a transcription engine, and any caller
        # that treats this as verbatim will eventually be wrong.
        "verbatim": False,
        "confidence": (
            "none"
            if empty
            else "low"
            if unreadable > 3 or outcome["image"].get("likely_legible") is False
            else "medium"
        ),
        "caveat": (
            "transcribed by a vision language model, which predicts text rather "
            "than reading it optically. Verify any value used for a decision "
            "against the source document or instrument."
        ),
        "model": outcome.get("model"),
        "provider": outcome.get("provider"),
        "image": outcome.get("image"),
    }


__all__ = [
    "NO_TEXT_MARKER",
    "OCR_PROMPT",
    "OCR_SYSTEM",
    "PATTERNS",
    "extract_identifiers",
    "extract_text",
    "illegible_count",
]
