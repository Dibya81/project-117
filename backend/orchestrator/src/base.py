"""Orchestrator result envelope.

Every orchestrator/agent/workflow invocation returns an ``OrchestratorResult``.
Phases 6–8 populate the fields; the shape is fixed now so the API contract is
stable for the future frontend.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    document_id: str
    page: int | None = None
    section: str | None = None
    chunk_id: str | None = None


class OrchestratorResult(BaseModel):
    status: Literal["ok", "error", "not_implemented"]
    response: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)  # artifact ids
    trace: list[dict[str, Any]] = Field(default_factory=list)  # execution trace
    error: str | None = None