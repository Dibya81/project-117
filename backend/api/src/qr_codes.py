"""Equipment QR labels — one payload, one local renderer.

Every printed label in the plant encodes exactly one string::

    P117:EQUIP:<tag>          e.g.  P117:EQUIP:P-1001

WHY a namespace instead of a URL: the label belongs to this plant's Project 117
Android client, not to the generic camera app on whatever phone is nearby. An
``https://`` payload makes every camera offer to open a web page the plant floor
may not even be able to reach, and a bare tag is short enough that a scanner at
another site could act on a colliding code. ``P117:EQUIP:`` means nothing to any
app except this one, which strips it and resolves the tag against the real plant
dataset.

Labels are still accepted in all three forms by ``identify_equipment`` — prefixed
tag, bare tag and asset id — so anything printed before the namespace, and the
mobile DTO's own ``qr_code`` field (which carries the real tag), keep resolving.

WHY segno: pure-Python, zero dependencies and fully offline. The posture in
``backend/security/egress.py`` refuses outbound calls, so a hosted QR service is
never an option; rendering is deterministic, so results are cached rather than
recomputed per request.
"""

from __future__ import annotations

import io
from functools import lru_cache
from typing import Any

import segno

#: Namespace every Project 117 equipment label carries (see module docstring).
QR_PREFIX = "P117:EQUIP:"

#: Error-correction level "H" recovers roughly 30% of a damaged symbol. A label
#: bolted to a machine is expected to get scuffed, and the redundancy is free.
_QR_ERROR = "h"

#: Nominal module size / quiet zone for the vector symbol. The console sizes the
#: rendered result with CSS, so these only set the intrinsic pixel box.
_QR_SCALE = 4
_QR_BORDER = 2


class MalformedQRCode(ValueError):
    """The scanned text claims the Project 117 namespace but carries no tag."""

    reason = "malformed_qr_code"
    status_code = 422


def equipment_tag(row: dict[str, Any]) -> str | None:
    """The real plant tag for an ``OperationsStore`` equipment row.

    ``OperationsStore._map_equipment`` packs ``[kind, area_id, tag]`` into
    ``tags``; the tag is the identifier a physical label encodes *and* the value
    the store's index resolves, so the label and the lookup cannot drift apart.
    """
    tags = row.get("tags") or []
    return str(tags[-1]) if tags else None


def qr_payload(tag: str) -> str:
    """The exact string a Project 117 equipment QR label encodes."""
    return f"{QR_PREFIX}{tag}"


def resolve_scanned_code(raw: str) -> str:
    """Normalise one scanned label to the code the equipment index resolves.

    Strips the Project 117 namespace and nothing else: a bare tag or asset id is
    returned unchanged, so the caller's existing id/tag lookup still decides.
    A payload that carries the prefix but no tag is *malformed* (422), never a
    lookup of the empty string — a guess here would be exactly the "closest
    match" behaviour this API deliberately does not have.
    """
    code = (raw or "").strip()
    if not code.startswith(QR_PREFIX):
        return code
    tag = code[len(QR_PREFIX) :].strip()
    if not tag:
        raise MalformedQRCode(f"QR code uses the {QR_PREFIX} prefix but carries no equipment tag")
    return tag


@lru_cache(maxsize=4096)
def qr_svg(payload: str) -> str:
    """Render ``payload`` as a standalone, inline-safe SVG document.

    The XML declaration is omitted (``xmldecl=False``) so the identical string
    can be served as ``image/svg+xml`` *and* placed in the console DOM without a
    second format; the SVG namespace is kept, so it is still valid standalone.
    Results are cached — a tag's symbol never changes, and a label sheet renders
    the same assets on every visit.
    """
    qr = segno.make(payload, error=_QR_ERROR)
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=_QR_SCALE, border=_QR_BORDER, xmldecl=False)
    return buffer.getvalue().decode("utf-8")


__all__ = [
    "QR_PREFIX",
    "MalformedQRCode",
    "equipment_tag",
    "qr_payload",
    "qr_svg",
    "resolve_scanned_code",
]
