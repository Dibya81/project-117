"""Artifact specifications (Phase 10).

The division of labour that makes generated files trustworthy:

    model -> ArtifactSpec (data) -> static generator -> sandbox -> file

The model writes **content and structure**. It does not write the file, and it
does not write the code that writes the file. The spec travels into the
sandbox as JSON *data* and is rendered by a script that was reviewed once (see
``generators/``). Model-authored python-pptx code would have to be reviewed on
every single run, which is not a thing anyone does.

Everything here is bounded - slide counts, text length, sheet sizes - because
these numbers become memory and CPU in a container, and because a 4000-slide
deck is a symptom rather than a request.

Notable omission: **no formulas anywhere in the spreadsheet model.** A formula
is code, and a formula invented by a language model is unreviewed code that a
spreadsheet will evaluate on the recipient's machine. Numbers are computed in
the sandbox, checked by the calculation checker, and written as values.

Citations are first-class on bullets and sections. "Cite the source pages for
every major claim" is a structural property of the artifact, so the citation
checker can walk the spec and compare it against retrieved evidence rather
than parsing prose out of a finished file.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ArtifactType = Literal["pptx", "docx", "xlsx", "pdf"]

#: Bounds. Generous for real work, small enough that abuse is obvious.
MAX_SLIDES = 60
MAX_SECTIONS = 200
MAX_SHEETS = 20
MAX_ROWS_PER_SHEET = 5000
MAX_TEXT = 4000

#: Excel rejects these in a sheet name.
_ILLEGAL_SHEET_CHARS = set(r"[]:*?/\\")


class SpecError(ValueError):
    """The requested artifact is not something we will build."""

    reason = "artifact_spec_invalid"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=128)
    page: int | None = Field(default=None, ge=1)
    section: str = Field(default="", max_length=300)
    chunk_id: str = Field(default="", max_length=128)

    def label(self) -> str:
        parts = [self.document_id]
        if self.page:
            parts.append(f"p. {self.page}")
        if self.section:
            parts.append(self.section)
        return " - ".join(parts)


class Bullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_TEXT)
    citations: list[Citation] = Field(default_factory=list, max_length=6)


class Slide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    #: Eight bullets is roughly what fits before python-pptx starts shrinking
    #: text to illegibility. The artifact checker flags overflow independently.
    bullets: list[Bullet] = Field(default_factory=list, max_length=8)
    notes: str = Field(default="", max_length=MAX_TEXT)
    layout: Literal["title", "title_content", "section", "two_content"] = "title_content"


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=300)
    level: int = Field(default=1, ge=1, le=4)
    paragraphs: list[str] = Field(default_factory=list, max_length=40)
    bullets: list[Bullet] = Field(default_factory=list, max_length=40)
    citations: list[Citation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _cap_paragraphs(self) -> Section:
        for paragraph in self.paragraphs:
            if len(paragraph) > MAX_TEXT:
                raise ValueError(f"a paragraph exceeds {MAX_TEXT} characters")
        return self


class Sheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=31)
    columns: list[str] = Field(min_length=1, max_length=64)
    #: Row cells are values only - str, number, bool or null. No formulas.
    rows: list[list[str | float | int | bool | None]] = Field(
        default_factory=list, max_length=MAX_ROWS_PER_SHEET
    )
    freeze_header: bool = True

    @model_validator(mode="after")
    def _rows_match_columns(self) -> Sheet:
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"sheet '{self.name}' row {index + 1} has {len(row)} cells, "
                    f"expected {width}"
                )
        return self

    @model_validator(mode="after")
    def _no_illegal_chars(self) -> Sheet:
        if set(self.name) & _ILLEGAL_SHEET_CHARS:
            raise ValueError(f"sheet name '{self.name}' contains characters Excel rejects")
        return self


class ArtifactSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ArtifactType
    title: str = Field(min_length=1, max_length=300)
    subtitle: str = Field(default="", max_length=300)
    author: str = Field(default="Project 117", max_length=120)
    slides: list[Slide] = Field(default_factory=list, max_length=MAX_SLIDES)
    sections: list[Section] = Field(default_factory=list, max_length=MAX_SECTIONS)
    sheets: list[Sheet] = Field(default_factory=list, max_length=MAX_SHEETS)
    #: Every source used, for the trailing sources page/sheet.
    sources: list[Citation] = Field(default_factory=list, max_length=200)
    footer: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _content_matches_type(self) -> ArtifactSpec:
        if self.type == "pptx":
            if not self.slides:
                raise ValueError("a pptx spec must contain at least one slide")
            if self.sheets:
                raise ValueError("a pptx spec cannot contain sheets")
        elif self.type in ("docx", "pdf"):
            if not self.sections:
                raise ValueError(f"a {self.type} spec must contain at least one section")
            if self.sheets:
                raise ValueError(f"a {self.type} spec cannot contain sheets")
        elif self.type == "xlsx":
            if not self.sheets:
                raise ValueError("an xlsx spec must contain at least one sheet")
            if self.slides or self.sections:
                raise ValueError("an xlsx spec cannot contain slides or sections")
        return self

    def all_citations(self) -> list[Citation]:
        """Every citation in the document, in reading order, plus sources."""
        found: list[Citation] = []
        for slide in self.slides:
            for bullet in slide.bullets:
                found.extend(bullet.citations)
        for section in self.sections:
            found.extend(section.citations)
            for bullet in section.bullets:
                found.extend(bullet.citations)
        found.extend(self.sources)
        return found

    def content_units(self) -> int:
        """Slides, sections or sheets - whatever this type counts in.

        Used by the artifact checker: "the request asked for ten slides, the
        file has ten slides" is a check, not an assumption.
        """
        if self.type == "pptx":
            return len(self.slides)
        if self.type == "xlsx":
            return len(self.sheets)
        return len(self.sections)

    def summary(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "content_units": self.content_units(),
            "citations": len(self.all_citations()),
            "sources": len(self.sources),
        }


def parse_spec(payload: dict[str, Any], *, expected_type: str | None = None) -> ArtifactSpec:
    """Validate a model-authored spec.

    Raises :class:`SpecError` with a message intended to be handed back to the
    planner, so a malformed spec becomes a retryable correction rather than a
    500.
    """
    if not isinstance(payload, dict):
        raise SpecError("artifact spec must be a JSON object")
    if expected_type and payload.get("type") not in (None, expected_type):
        raise SpecError(
            f"spec declares type '{payload.get('type')}' but '{expected_type}' was requested"
        )
    if expected_type:
        payload = {**payload, "type": expected_type}
    try:
        return ArtifactSpec.model_validate(payload)
    except Exception as exc:
        raise SpecError(f"artifact spec is not usable: {exc}") from exc
