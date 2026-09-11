from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

from backend.observability.metrics import request_id_var

logger = logging.getLogger(__name__)

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class Span:
    name: str
    trace_id: str
    job_id: str | None
    started_at: float
    ended_at: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return self.ended_at - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "job_id": self.job_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "attributes": self.attributes,
            "error": self.error,
        }


class AgentTraceRecorder:
    def __init__(self, *, max_spans_per_job: int = 500) -> None:
        self._max_spans_per_job = max(1, max_spans_per_job)
        self._spans_by_job: dict[str, list[Span]] = {}

    def record(self, span: Span) -> None:
        if not span.job_id:
            return
        bucket = self._spans_by_job.setdefault(span.job_id, [])
        bucket.append(span)
        if len(bucket) > self._max_spans_per_job:
            del bucket[: len(bucket) - self._max_spans_per_job]

    def spans_for_job(self, job_id: str) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self._spans_by_job.get(job_id, [])]

    def clear_job(self, job_id: str) -> None:
        self._spans_by_job.pop(job_id, None)


@contextmanager
def trace_span(
    name: str,
    *,
    recorder: AgentTraceRecorder | None = None,
    job_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Span]:
    trace_id = trace_id_var.get() or new_trace_id()
    trace_token = trace_id_var.set(trace_id)
    resolved_job_id = job_id or job_id_var.get()
    job_token = job_id_var.set(resolved_job_id) if resolved_job_id else None
    span = Span(
        name=name,
        trace_id=trace_id,
        job_id=resolved_job_id,
        started_at=time.perf_counter(),
        attributes=dict(attributes or {}),
    )
    try:
        yield span
    except Exception as exc:
        span.error = str(exc)
        raise
    finally:
        span.ended_at = time.perf_counter()
        request_id = request_id_var.get()
        if request_id:
            span.attributes.setdefault("request_id", request_id)
        if recorder is not None:
            recorder.record(span)
        else:
            logger.debug("trace span: %s", span.to_dict())
        trace_id_var.reset(trace_token)
        if job_token is not None:
            job_id_var.reset(job_token)
