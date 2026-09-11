"""Task classifier.

Picks the *model role* a task should use. Deterministic and keyword-driven on
purpose: asking a model which model to use costs a round trip, is not
reproducible, and fails exactly when the model layer is already unhealthy.

Honesty about what this is: a rule table with a confidence *score*, not a
trained classifier and not a calibrated probability. ``confidence`` orders
candidates and drives the weak-signal default; it must never be shown to a
user as an accuracy figure.

Design decision worth noting -- **modality is never inferred from prose.**
``vision`` is selected only when actual image inputs are present, and
``embedding``/``reranker`` only when the retrieval layer asks for them
explicitly. A task that says "look at this drawing" without attaching one
cannot be served by a vision model, so routing it there would turn a missing
attachment into a confusing model error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REASONING = "reasoning"
VISION = "vision"
EMBEDDING = "embedding"
RERANKER = "reranker"
CODING = "coding"
DOMAIN = "domain"

KNOWN_ROLES: tuple[str, ...] = (
    REASONING,
    VISION,
    EMBEDDING,
    RERANKER,
    CODING,
    DOMAIN,
)

# Prose signals only ever distinguish the three *text* roles.
CODING_TERMS: frozenset[str] = frozenset(
    {
        "python",
        "script",
        "code",
        "regex",
        "sql",
        "traceback",
        "stack trace",
        "exception",
        "refactor",
        "compile",
        "json schema",
        "yaml",
        "parse",
        "dataframe",
        "pandas",
        "unit test",
        "endpoint",
        "debug",
    }
)

DOMAIN_TERMS: frozenset[str] = frozenset(
    {
        "vibration",
        "bearing",
        "compressor",
        "pump",
        "turbine",
        "psv",
        "hazop",
        "p&id",
        "sop",
        "lockout",
        "tagout",
        "rpm",
        "cavitation",
        "seal",
        "lubrication",
        "overhaul",
        "maintenance",
        "work order",
        "preventive",
        "corrosion",
        "turnaround",
        "shutdown",
        "heat exchanger",
        "hydrotreater",
        "impeller",
        "alignment",
        "thrust",
        "flange",
        "gasket",
        "root cause",
        "failure mode",
    }
)

# Multi-word terms cannot be found by word tokenisation, so they are matched
# as substrings first and skipped during the token pass.
_ALL_TERMS = CODING_TERMS | DOMAIN_TERMS
_MULTI_WORD = tuple(term for term in _ALL_TERMS if " " in term or "&" in term)
_WORD_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class Classification:
    """Which role a task should use, and why."""

    role: str
    confidence: float
    reasons: tuple[str, ...]
    signals: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
            "signals": list(self.signals),
            "method": "rule_table",
            "caveat": (
                "confidence is a heuristic score, not a calibrated probability"
            ),
        }


def _matched_terms(text: str, terms: frozenset[str]) -> tuple[str, ...]:
    lowered = (text or "").lower()
    found: set[str] = set()
    for term in _MULTI_WORD:
        if term in terms and term in lowered:
            found.add(term)
    words = set(_WORD_RE.findall(lowered))
    for term in terms:
        if " " in term or "&" in term:
            continue
        if term in words:
            found.add(term)
    return tuple(sorted(found))


def classify(
    task: str,
    *,
    has_images: bool = False,
    wants_embedding: bool = False,
    wants_rerank: bool = False,
    explicit_role: str | None = None,
) -> Classification:
    """Classify one task into a model role.

    Precedence is deliberate: an explicit request beats an inferred one, and a
    hard modality requirement (images) beats any prose signal, because no
    amount of keyword matching makes a text-only model able to see.
    """
    if explicit_role is not None:
        role = str(explicit_role).strip()
        if role not in KNOWN_ROLES:
            raise ValueError(
                f"unknown model role '{explicit_role}' "
                f"(known: {', '.join(KNOWN_ROLES)})"
            )
        return Classification(
            role=role,
            confidence=1.0,
            reasons=("the caller named the role explicitly",),
        )

    if has_images:
        return Classification(
            role=VISION,
            confidence=1.0,
            reasons=(
                "image inputs are present and no text-only role can read them",
            ),
            signals=("images",),
        )

    if wants_rerank:
        return Classification(
            role=RERANKER,
            confidence=1.0,
            reasons=("the retrieval layer asked for reranking",),
            signals=("rerank",),
        )

    if wants_embedding:
        return Classification(
            role=EMBEDDING,
            confidence=1.0,
            reasons=("the retrieval layer asked for vectors",),
            signals=("embedding",),
        )

    text = task or ""
    if not text.strip():
        return Classification(
            role=REASONING,
            confidence=0.3,
            reasons=("the task text was empty; defaulted to the reasoning role",),
        )

    coding_hits = _matched_terms(text, CODING_TERMS)
    domain_hits = _matched_terms(text, DOMAIN_TERMS)

    # Domain wins ties. In this product a sentence containing both "script"
    # and "compressor vibration" is a plant question that happens to mention
    # tooling, not a programming question.
    if domain_hits and len(domain_hits) >= len(coding_hits):
        reasons = ["the task uses plant/maintenance vocabulary"]
        if coding_hits:
            reasons.append("domain vocabulary outweighed or tied the code signal")
        return Classification(
            role=DOMAIN,
            confidence=min(0.9, 0.55 + 0.1 * len(domain_hits)),
            reasons=tuple(reasons),
            signals=domain_hits,
        )

    if coding_hits:
        return Classification(
            role=CODING,
            confidence=min(0.9, 0.55 + 0.1 * len(coding_hits)),
            reasons=("the task refers to code, data wrangling or debugging",),
            signals=coding_hits,
        )

    return Classification(
        role=REASONING,
        confidence=0.4,
        reasons=("no strong signal; defaulted to the general reasoning role",),
    )


__all__ = [
    "CODING",
    "CODING_TERMS",
    "Classification",
    "DOMAIN",
    "DOMAIN_TERMS",
    "EMBEDDING",
    "KNOWN_ROLES",
    "REASONING",
    "RERANKER",
    "VISION",
    "classify",
]
