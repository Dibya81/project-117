"""Task decomposition (Phase 6).

Splits a compound request into ordered sub-tasks. "Read this manual, list the
recommended overhaul intervals, and then build me a ten-slide deck citing the
pages" is three asks with a dependency between the second and the third, and a
system that treats it as one string will answer the first and quietly drop the
rest.

**This module contains no model call, on purpose.** Decomposition is where a
language model is most tempting and least trustworthy: asked to split a
request it will happily add a sub-task nobody asked for ("and recommend next
steps"), drop the inconvenient half of a sentence, or reorder two steps whose
order mattered. All three failures are invisible in the final answer, because
the answer is fluent either way. So the split here is deterministic, boring and
readable - sentence and clause boundaries, an explicit sequencing-cue list, and
a verb list for "this sub-task produces a file".

The decomposition is *advice*. The planner owns plan construction and the
router owns intent; this module only reports the structure it can see, and the
planner remains free to build a single-pass plan anyway. Keeping it advisory is
what stops it from becoming a second planner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: More than this and the request is a document, not a task. The tail is
#: merged rather than dropped, so nothing the user asked for disappears.
MAX_SUBTASKS = 6

#: Shorter fragments ("and cite it", "in detail") are modifiers, not tasks.
MIN_SUBTASK_CHARS = 14

#: A fragment beginning with one of these depends on the fragment before it.
#: This is the ordering signal; without it sub-tasks are independent and the
#: planner may run them in one wave.
_SEQUENCE_CUES = (
    "then",
    "after that",
    "afterwards",
    "next",
    "finally",
    "lastly",
    "once done",
    "once that",
    "using that",
    "using the",
    "based on that",
    "based on the above",
    "from that",
    "with those",
    "and then",
)

#: Verbs that mean "do something" rather than "tell me something". Used only
#: to label a sub-task, never to grant a permission - risk lives in the tool
#: registry.
_ACTION_VERBS = (
    "analyse",
    "analyze",
    "build",
    "calculate",
    "compare",
    "compile",
    "compute",
    "create",
    "draft",
    "estimate",
    "export",
    "extract",
    "find",
    "generate",
    "identify",
    "list",
    "make",
    "plan",
    "prepare",
    "produce",
    "read",
    "review",
    "summarise",
    "summarize",
    "write",
)

#: Deliverable nouns. A sub-task that pairs a producing verb with one of these
#: is expected to end in an artifact step.
_ARTIFACT_NOUNS = (
    "deck",
    "docx",
    "document",
    "excel",
    "file",
    "pdf",
    "powerpoint",
    "ppt",
    "pptx",
    "presentation",
    "report",
    "slide",
    "slides",
    "spreadsheet",
    "workbook",
    "xlsx",
)

_PRODUCING_VERBS = (
    "build",
    "create",
    "draft",
    "export",
    "generate",
    "make",
    "prepare",
    "produce",
    "write",
)

#: Sentence boundary: terminator followed by whitespace. Kept simple because
#: over-clever splitting breaks on "7.1 mm/s" and "rev. 3".
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+")

#: Enumerated requests: "1. read the manual  2. build the deck".
_ENUMERATION_SPLIT = re.compile(r"(?:^|\s)(?:\(?\d{1,2}[).]|[-*\u2022])\s+")

#: Clause split on a sequencing conjunction, keeping the cue with the clause
#: that follows it so the dependency is detectable afterwards.
_CLAUSE_SPLIT = re.compile(
    r"\s*,?\s+(?=(?:and\s+then|then|after\s+that|afterwards|next|finally|lastly)\b)",
    re.IGNORECASE,
)

#: Protects decimals and abbreviations from the sentence splitter.
_PROTECT = re.compile(r"(\d)\.(\d)")


@dataclass
class SubTask:
    id: str
    text: str
    #: The leading action verb, when one is recognisable. Advisory label only.
    verb: str = ""
    depends_on: list[str] = field(default_factory=list)
    #: True when this sub-task is expected to produce a file.
    expects_artifact: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "verb": self.verb,
            "depends_on": list(self.depends_on),
            "expects_artifact": self.expects_artifact,
        }


@dataclass
class Decomposition:
    task: str
    subtasks: list[SubTask] = field(default_factory=list)
    #: "single" when the request was left whole, "split" when it was divided.
    origin: str = "single"
    notes: list[str] = field(default_factory=list)

    @property
    def is_compound(self) -> bool:
        return len(self.subtasks) > 1

    @property
    def expects_artifact(self) -> bool:
        return any(item.expects_artifact for item in self.subtasks)

    def sequential(self) -> bool:
        """True when every sub-task after the first depends on its predecessor."""
        return self.is_compound and all(item.depends_on for item in self.subtasks[1:])

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "origin": self.origin,
            "compound": self.is_compound,
            "sequential": self.sequential(),
            "expects_artifact": self.expects_artifact,
            "subtasks": [item.to_dict() for item in self.subtasks],
            "notes": list(self.notes),
        }

    def summary(self) -> dict[str, Any]:
        """Compact form for the job trace - counts, not content."""
        return {
            "origin": self.origin,
            "subtasks": len(self.subtasks),
            "compound": self.is_compound,
            "sequential": self.sequential(),
            "expects_artifact": self.expects_artifact,
        }


class TaskDecomposer:
    """Deterministic splitter. Constructed without dependencies on purpose."""

    def __init__(self, *, max_subtasks: int = MAX_SUBTASKS) -> None:
        self._max = max(1, int(max_subtasks))

    def decompose(self, task: str) -> Decomposition:
        cleaned = " ".join((task or "").split())
        if not cleaned:
            return Decomposition(task="", origin="single", notes=["no task was given"])

        fragments = self._fragments(cleaned)
        fragments = self._merge_short(fragments)

        if len(fragments) <= 1:
            return Decomposition(
                task=cleaned,
                subtasks=[self._subtask("t1", cleaned, previous=None)],
                origin="single",
            )

        notes: list[str] = []
        if len(fragments) > self._max:
            # Merging the tail keeps every ask in the plan. Truncating would
            # silently drop the last thing the user said, which is exactly the
            # failure this module exists to prevent.
            head = fragments[: self._max - 1]
            tail = " ".join(fragments[self._max - 1 :])
            fragments = [*head, tail]
            notes.append(
                f"request contained more than {self._max} asks; the remainder was merged "
                "into the final sub-task"
            )

        subtasks: list[SubTask] = []
        for index, fragment in enumerate(fragments, start=1):
            previous = subtasks[-1].id if subtasks else None
            subtasks.append(self._subtask(f"t{index}", fragment, previous=previous))

        return Decomposition(task=cleaned, subtasks=subtasks, origin="split", notes=notes)

    # --- internals --------------------------------------------------------

    def _fragments(self, text: str) -> list[str]:
        enumerated = [part.strip() for part in _ENUMERATION_SPLIT.split(text) if part.strip()]
        if len(enumerated) > 1:
            return enumerated

        protected = _PROTECT.sub(r"\1<DOT>\2", text)
        pieces: list[str] = []
        for sentence in _SENTENCE_SPLIT.split(protected):
            sentence = sentence.replace("<DOT>", ".").strip()
            if not sentence:
                continue
            pieces.extend(
                clause.strip() for clause in _CLAUSE_SPLIT.split(sentence) if clause.strip()
            )
        return pieces or [text]

    @staticmethod
    def _merge_short(fragments: list[str]) -> list[str]:
        """Fold modifiers back into the ask they modify."""
        merged: list[str] = []
        for fragment in fragments:
            stripped = fragment.strip(" .;,")
            if not stripped:
                continue
            if merged and len(stripped) < MIN_SUBTASK_CHARS:
                merged[-1] = f"{merged[-1]} {stripped}".strip()
                continue
            merged.append(stripped)
        return merged

    def _subtask(self, identifier: str, text: str, *, previous: str | None) -> SubTask:
        lowered = text.lower()
        depends_on: list[str] = []
        if previous and any(lowered.startswith(cue) for cue in _SEQUENCE_CUES):
            depends_on = [previous]
        elif previous and any(f" {cue} " in f" {lowered} " for cue in ("using that", "from that")):
            depends_on = [previous]

        verb = ""
        for candidate in _ACTION_VERBS:
            if re.search(rf"\b{candidate}\b", lowered):
                verb = candidate
                break

        expects_artifact = any(
            re.search(rf"\b{producer}\b", lowered) for producer in _PRODUCING_VERBS
        ) and any(re.search(rf"\b{noun}\b", lowered) for noun in _ARTIFACT_NOUNS)

        return SubTask(
            id=identifier,
            text=text,
            verb=verb,
            depends_on=depends_on,
            expects_artifact=expects_artifact,
        )


def decompose(task: str, *, max_subtasks: int = MAX_SUBTASKS) -> Decomposition:
    """Convenience wrapper for callers that do not need to hold an instance."""
    return TaskDecomposer(max_subtasks=max_subtasks).decompose(task)
