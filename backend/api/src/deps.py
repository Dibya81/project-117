"""Accessors for services attached to ``app.state`` by the app factory."""

from __future__ import annotations

from starlette.requests import Request

from backend.config import Settings
from backend.deliverables.service import ArtifactService
from backend.ingestion.service import IngestionService
from backend.jobs.bus import JobEventBus
from backend.jobs.service import JobService
from backend.memory import MemoryService
from backend.observability.metrics import MetricsRegistry
from backend.orchestrator import Orchestrator
from backend.rag.service import RetrievalService
from backend.sandbox.policy import SandboxPolicy
from backend.sandbox.service import SandboxService
from backend.security.approvals import ApprovalPolicy
from backend.security.audit import AuditService
from backend.security.rbac import Principal
from backend.storage.documents import DocumentStorage
from backend.storage.operations import OperationsStore
from backend.tools.registry import ToolRegistry
from backend.verification.verifier import Verifier


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_documents(request: Request) -> DocumentStorage:
    return request.app.state.documents


def get_audit(request: Request) -> AuditService:
    return request.app.state.audit


def get_metrics(request: Request) -> MetricsRegistry:
    return request.app.state.metrics


def get_ingestion(request: Request) -> IngestionService:
    return request.app.state.ingestion


def get_retrieval(request: Request) -> RetrievalService:
    return request.app.state.retrieval


def get_principal(request: Request) -> Principal:
    """The authenticated (or anonymous) caller for this request (Phase 12).

    Thin re-export so routers depend on ``api.deps`` uniformly rather than
    reaching into ``security.auth`` directly; the real resolution/caching
    logic lives there.
    """
    from backend.security.auth import get_principal as _get_principal

    return _get_principal(request)


def get_sandbox_policy(request: Request) -> SandboxPolicy:
    return request.app.state.sandbox_policy


def get_sandbox(request: Request) -> SandboxService:
    return request.app.state.sandbox


def get_approval_policy(request: Request) -> ApprovalPolicy:
    return request.app.state.approval_policy


def get_tools(request: Request) -> ToolRegistry:
    return request.app.state.tools


def get_artifacts(request: Request) -> ArtifactService:
    return request.app.state.artifacts


def get_verifier(request: Request) -> Verifier:
    return request.app.state.verifier


def get_jobs(request: Request) -> JobService:
    return request.app.state.jobs


def get_job_bus(request: Request) -> JobEventBus:
    return request.app.state.job_bus


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


def get_memory(request: Request) -> MemoryService:
    return request.app.state.memory


def get_operations(request: Request) -> OperationsStore:
    """Operations records (equipment, work orders, approvals, analytics).

    Equipment is rehydrated from the real plant dataset in the simulation
    SQLite store; runtime work orders and approval decisions are persisted in
    ``P117_OPERATIONS_DB`` (default ``data/operations.db``). See
    ``backend/storage/operations.py``. Cached on ``app.state`` so runtime
    mutations (a created work order, a recorded approval decision) are served
    from the same store across requests.
    """
    store = getattr(request.app.state, "operations", None)
    if store is None:
        settings = request.app.state.settings
        store = OperationsStore(
            db_path=settings.operations_db,
            default_plant=settings.operations_plant,
        )
        request.app.state.operations = store
    return store