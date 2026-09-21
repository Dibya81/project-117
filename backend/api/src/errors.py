"""Structured API errors.

Every error response uses the envelope
``{"error": {"code": ..., "message": ..., "phase": ...}}`` so the future
frontend can branch on stable codes.
"""

from __future__ import annotations


class APIError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(
        self, message: str, *, phase: int | None = None, detail: dict | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.phase = phase
        self.detail = detail

    def payload(self) -> dict:
        error: dict = {"code": self.code, "message": self.message, "phase": self.phase}
        if self.detail:
            error["detail"] = self.detail
        return {"error": error}


class EndpointNotImplemented(APIError):
    """Explicit 501 — the endpoint is real but its phase has not landed."""

    status_code = 501
    code = "not_implemented"


class NotFound(APIError):
    status_code = 404
    code = "not_found"


class BadRequest(APIError):
    status_code = 400
    code = "bad_request"


class ServiceUnavailable(APIError):
    status_code = 503
    code = "service_unavailable"

    def __init__(
        self,
        message: str,
        *,
        phase: int | None = None,
        detail: dict | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message, phase=phase, detail=detail)
        if code:
            self.code = code
