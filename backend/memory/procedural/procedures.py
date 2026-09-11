"""Procedural memory: how work is actually done here.

A procedure is an ordered list of steps with a source. The source is what
makes it usable in an answer - "isolate, lock out, verify zero energy" is
only actionable if the reader can see it came from SOP-11.2 rev 4 and not
from a model's general idea of maintenance.

Parsing is intentionally conservative: numbered or bulleted lines become
steps, everything else is ignored. A loose paragraph is not silently
reinterpreted as a safety procedure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from backend.memory.src.memory_types import (
    KIND_PROCEDURAL,
    SCOPE_GLOBAL,
    MemoryCandidate,
)

_NUMBERED = re.compile(r"^\s*(?:\d+[.)]|[-*\u2022])\s+(.*\S)\s*$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*\S)\s*$")

MAX_STEPS = 40
MAX_STEP_CHARS = 400


@dataclass(frozen=True)
class Procedure:
    """An ordered, sourced sequence of steps."""

    name: str
    steps: tuple[str, ...] = ()
    source_document: str | None = None
    revision: str | None = None
    equipment: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def sourced(self) -> bool:
        """False means this must not be presented as the plant's procedure."""
        return bool(self.source_document)

    def as_text(self) -> str:
        lines = [f"{index}. {step}" for index, step in enumerate(self.steps, start=1)]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "steps": list(self.steps),
            "sourceDocument": self.source_document,
            "revision": self.revision,
            "equipment": list(self.equipment),
            "sourced": self.sourced,
        }

    def to_candidate(self, *, scope: str = SCOPE_GLOBAL) -> MemoryCandidate:
        evidence: list[dict[str, Any]] = []
        if self.source_document:
            evidence.append(
                {"document_id": self.source_document, "section": self.name, "revision": self.revision}
            )
        return MemoryCandidate(
            kind=KIND_PROCEDURAL,
            key=self.name,
            content=self.as_text(),
            scope=scope,
            evidence=evidence,
            # An unsourced procedure is remembered at low confidence rather
            # than refused, but it can never outrank a sourced one.
            confidence=0.75 if self.sourced else 0.35,
            metadata={
                "revision": self.revision,
                "equipment": list(self.equipment),
                "stepCount": self.step_count,
                **{k: v for k, v in self.metadata.items() if isinstance(v, (str, int, float))},
            },
        )


def parse_steps(text: str) -> list[str]:
    """Extract numbered or bulleted steps, in document order."""
    steps: list[str] = []
    for line in (text or "").splitlines():
        match = _NUMBERED.match(line)
        if not match:
            continue
        step = match.group(1).strip()[:MAX_STEP_CHARS]
        if step:
            steps.append(step)
        if len(steps) >= MAX_STEPS:
            break
    return steps


def from_markdown(
    text: str,
    *,
    name: str | None = None,
    source_document: str | None = None,
    revision: str | None = None,
    equipment: Sequence[str] = (),
) -> Procedure:
    """Build a procedure from an SOP or manual excerpt.

    The name falls back to the first heading, then to the source id - never
    to an invented title.
    """
    heading = None
    for line in (text or "").splitlines():
        found = _HEADING.match(line)
        if found:
            heading = found.group(1).strip()
            break
    return Procedure(
        name=(name or heading or source_document or "untitled procedure").strip(),
        steps=tuple(parse_steps(text)),
        source_document=source_document,
        revision=revision,
        equipment=tuple(equipment or ()),
    )


__all__ = ["MAX_STEPS", "Procedure", "from_markdown", "parse_steps"]
