"""Request/response contracts shared by routes, tests, and the OpenAPI export.

The route modules import their payload models from here so a contract has one
definition in the codebase. Domain models (jobs, plans, verification reports)
stay in their own packages; only the HTTP wire shapes live here.
"""

from backend.api.src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    Citation,
)
from backend.api.src.schemas.document import (
    DocumentListResponse,
    DocumentOut,
    DocumentStatus,
    ReindexResponse,
    UploadResponse,
)
from backend.api.src.schemas.workflow import (
    RunStatus,
    WorkflowRunRequest,
    WorkflowRunView,
    WorkflowStepView,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ChatStreamEvent",
    "Citation",
    "DocumentListResponse",
    "DocumentOut",
    "DocumentStatus",
    "ReindexResponse",
    "RunStatus",
    "UploadResponse",
    "WorkflowRunRequest",
    "WorkflowRunView",
    "WorkflowStepView",
]
