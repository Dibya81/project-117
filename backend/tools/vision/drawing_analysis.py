"""Engineering-drawing analysis (P&IDs, isometrics, GA drawings).

Asking a vision model about a P&ID is useful and dangerous in the same breath:
it is good at reading the sheet, and it will invent a tag number that looks
exactly like the ones around it. The mitigation here is structural.

1. The model is asked for **strict JSON** in a fixed shape, and the response is
   parsed rather than read. A response that is not JSON is a failure, not a
   result to summarise.
2. Every tag the model returns is checked against
   :data:`backend.tools.vision.ocr.PATTERNS` for shape, and - when the caller
   supplies a registry of known tags - against that registry. Tags that pass
   neither are returned under ``unverified_tags``, never merged into the
   confirmed list.
3. The caller always receives ``verified``/``unverified`` as separate keys, so
   "the model said this" and "this exists" cannot be confused downstream.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from backend.tools.base import ToolContext, ToolError
from backend.tools.vision.image_analysis import analyse
from backend.tools.vision.ocr import PATTERNS

DRAWING_SYSTEM = (
    "You read industrial engineering drawings (P&IDs, isometrics, general "
    "arrangement drawings) and report only what is drawn on the sheet."
)

_SCHEMA_HINT = (
    '{"drawing_type": string, "title_block": {"title": string, "number": string, '
    '"revision": string}, "equipment": [{"tag": string, "description": string}], '
    '"instruments": [{"tag": string, "function": string}], "lines": [{"number": '
    'string, "service": string}], "notes": [string], "unreadable": [string]}'
)

DRAWING_PROMPT = (
    "Read this engineering drawing and return ONLY a JSON object, no prose and "
    "no code fence, matching exactly this shape:\n"
    f"{_SCHEMA_HINT}\n"
    "Rules:\n"
    "- Include an item only if you can actually read its tag on the sheet.\n"
    "- Never invent, complete or pattern-match a tag number. If a tag is partly "
    "legible, put what you can see in 'unreadable' and omit it from the lists.\n"
    "- Use an empty array for anything the drawing does not show.\n"
    "- Copy identifiers exactly as printed, including prefixes and suffixes."
)

_LIST_FIELDS = ("equipment", "instruments", "lines", "notes", "unreadable")

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def _strip_fence(text: str) -> str:
    return _FENCE.sub("", str(text or "")).strip()


def parse_response(text: str) -> dict[str, Any]:
    """Parse the model's JSON, or fail loudly.

    A vision model that returns prose here has not done the task. Salvaging
    the prose would produce a result indistinguishable from a real one, so
    this raises instead.
    """
    body = _strip_fence(text)
    if not body:
        raise ToolError("the vision model returned an empty response")
    try:
        parsed = json.loads(body)
    except ValueError:
        # One tolerated recovery: a model that wrapped the object in commentary.
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            raise ToolError(
                "the vision model did not return JSON; the drawing was not parsed "
                "(returning its prose as structured data would fabricate structure)"
            ) from None
        try:
            parsed = json.loads(body[start : end + 1])
        except ValueError as exc:
            raise ToolError(f"the vision model returned malformed JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ToolError(
            f"expected a JSON object describing the drawing, got {type(parsed).__name__}"
        )
    for field in _LIST_FIELDS:
        value = parsed.get(field)
        parsed[field] = list(value) if isinstance(value, list) else []
    title_block = parsed.get("title_block")
    parsed["title_block"] = title_block if isinstance(title_block, dict) else {}
    parsed["drawing_type"] = str(parsed.get("drawing_type") or "").strip()
    return parsed


def _tag_of(item: Any, key: str) -> str:
    if isinstance(item, dict):
        return str(item.get(key) or "").strip()
    return str(item or "").strip()


def verify_tags(
    items: Iterable[Any],
    *,
    key: str = "tag",
    pattern_name: str = "equipment_tag",
    known: Iterable[str] | None = None,
) -> dict[str, list[Any]]:
    """Split model-reported items into verified and unverified.

    ``known`` is the authoritative set (an equipment register, a line list).
    When supplied, matching it is what "verified" means; without it, the best
    available check is the documented identifier shape, and the result says so.
    """
    pattern = PATTERNS.get(pattern_name)
    registry = {str(tag).strip().upper() for tag in (known or []) if str(tag).strip()}
    verified: list[Any] = []
    unverified: list[Any] = []
    for item in items:
        tag = _tag_of(item, key)
        if not tag:
            unverified.append(item)
            continue
        shape_ok = bool(pattern.fullmatch(tag)) if pattern else True
        if registry:
            (verified if tag.upper() in registry else unverified).append(item)
        else:
            (verified if shape_ok else unverified).append(item)
    return {
        "verified": verified,
        "unverified": unverified,
        "basis": "registry" if registry else "pattern",
    }


async def analyse_drawing(
    context: ToolContext,
    *,
    data: bytes,
    question: str = "",
    known_equipment: Iterable[str] | None = None,
    known_lines: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Extract structure from a drawing image and verify what came back."""
    prompt = DRAWING_PROMPT
    if str(question or "").strip():
        prompt = (
            f"{DRAWING_PROMPT}\n\nThe reader is specifically interested in: "
            f"{str(question).strip()[:400]}. Still return only the JSON object."
        )

    outcome = await analyse(
        context,
        data=data,
        prompt=prompt,
        system=DRAWING_SYSTEM,
        temperature=0.0,
        max_tokens=2500,
    )
    parsed = parse_response(outcome.get("text", ""))

    equipment = verify_tags(
        parsed["equipment"], key="tag", pattern_name="equipment_tag", known=known_equipment
    )
    instruments = verify_tags(
        parsed["instruments"], key="tag", pattern_name="equipment_tag", known=known_equipment
    )
    lines = verify_tags(
        parsed["lines"], key="number", pattern_name="line_number", known=known_lines
    )

    unverified_total = (
        len(equipment["unverified"]) + len(instruments["unverified"]) + len(lines["unverified"])
    )
    return {
        "drawing_type": parsed["drawing_type"],
        "title_block": parsed["title_block"],
        "equipment": equipment["verified"],
        "instruments": instruments["verified"],
        "lines": lines["verified"],
        "unverified": {
            "equipment": equipment["unverified"],
            "instruments": instruments["unverified"],
            "lines": lines["unverified"],
        },
        "verification_basis": {
            "equipment": equipment["basis"],
            "instruments": instruments["basis"],
            "lines": lines["basis"],
        },
        "unreadable": parsed["unreadable"],
        "notes": parsed["notes"],
        "counts": {
            "equipment": len(equipment["verified"]),
            "instruments": len(instruments["verified"]),
            "lines": len(lines["verified"]),
            "unverified": unverified_total,
        },
        "method": "vision_model+pattern_verification",
        "caveat": (
            "tags under 'unverified' were reported by the model but did not match "
            "the register or the documented identifier shape. Do not cite them as "
            "existing plant items without checking the drawing by hand."
        ),
        "model": outcome.get("model"),
        "provider": outcome.get("provider"),
        "image": outcome.get("image"),
    }


__all__ = [
    "DRAWING_PROMPT",
    "DRAWING_SYSTEM",
    "analyse_drawing",
    "parse_response",
    "verify_tags",
]
