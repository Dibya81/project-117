"""Project 117 backend — FastAPI application factory.

Run:  uv run uvicorn backend.api.src.main:create_app --factory --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import __version__
from backend.agents import build_agent_registry
from backend.api.src.errors import APIError, EndpointNotImplemented
from backend.api.src.middleware import (
    PrincipalMiddleware,
    RateLimitMiddleware,
    RequestAuditMiddleware,
    RoutePermissionMiddleware,
)
from backend.api.src.routes import (
    agents,
    analytics,
    approvals,
    artifacts,
    audit,
    auth,
    chat,
    documents,
    equipment,
    health,
    jobs,
    knowledge,
    materials,
    mobile,
    models,
    network,
    sovereignty,
    tools,
    work_orders,
    workflows,
)
from backend.chat.service import ChatService
from backend.chat.sessions import ChatSessionStore
from backend.config import Settings
from backend.database.base import create_engine_for, create_session_factory, init_db
from backend.deliverables.service import ArtifactService
from backend.ingestion import (
    DocumentStager,
    IngestionError,
    IngestionService,
    LocalGPTIndexer,
    UnsupportedForIngestion,
)
from backend.jobs.bus import JobEventBus
from backend.jobs.service import JobService
from backend.logging_config import setup_logging
from backend.memory import MemoryService
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.providers.base import ModelProvider
from backend.models.providers.openai_compatible import OpenAICompatibleProvider
from backend.models.router import ModelRouter
from backend.observability.metrics import MetricsRegistry, RequestMetricsMiddleware
from backend.observability.traces import AgentTraceRecorder
from backend.orchestrator import (
    AgentManager,
    ContextManager,
    ExecutionManager,
    Orchestrator,
    Planner,
    RecoveryManager,
    TaskRouter,
    VerificationManager,
    WorkflowManager,
)
from backend.orchestrator.policies import (
    ActionPolicy,
    tool_policy_from_settings,
)
from backend.orchestrator.policies import (
    approval_policy_from_settings as plan_approval_policy_from_settings,
)
from backend.rag import RetrievalService
from backend.rag.adapter import LocalGPTRetriever
from backend.rag.errors import RetrievalError
from backend.sandbox.policy import policy_from_settings as sandbox_policy_from_settings
from backend.sandbox.service import SandboxService
from backend.security.approvals import policy_from_settings as approval_policy_from_settings
from backend.security.audit import AuditService
from backend.security.auth import AuthenticationError
from backend.security.egress import policy_from_settings
from backend.security.network.audit_sink import register_audit_sink
from backend.security.rbac import AuthorizationError
from backend.security.signing import load_or_create_key
from backend.simulation import api as simulation_api
from backend.simulation import datasets as sim_datasets
from backend.simulation.service import simulation_service
from backend.storage.documents import DocumentStorage, DocumentValidationError
from backend.storage.identity import DEFAULT_ENROLLMENT_CODES, IdentityStore
from backend.storage.materials import MaterialsStore
from backend.storage.mobile import MobileStore, default_mobile_db
from backend.tools.base import (
    ToolApprovalRequired,
    ToolArgumentError,
    ToolError,
    ToolNotFound,
    ToolPermissionDenied,
    ToolTimeout,
    ToolUnavailable,
)
from backend.tools.builtin import build_default_registry
from backend.verification.verifier import Verifier
from backend.workflows.engine.loader import load_registry

logger = logging.getLogger(__name__)


def _ollama_api_host(base_url: str) -> str:
    """localGPT's embedder expects the Ollama native API root (no /v1)."""
    return base_url.removesuffix("/v1").rstrip("/")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(level=settings.log_level, json_logs=settings.json_logs)

    engine = create_engine_for(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        init_db(engine)
        # The bus needs the running loop to hop threads safely (see jobs/bus.py);
        # it cannot be bound at construction time, before uvicorn starts one.
        app.state.job_bus.bind_loop()
        missing = settings.unconfigured_roles()
        if missing:
            # Say it once at boot rather than letting each request discover it.
            logger.warning(
                "model roles unconfigured: %s — requests for these roles return "
                "503 model_unavailable until set (see .env.example)",
                ", ".join(missing),
            )
        if bool(getattr(settings, "auth_required", False)) and not getattr(
            settings, "auth_api_key", ""
        ):
            logger.warning(
                "P117_AUTH_REQUIRED=true but P117_AUTH_API_KEY is not set; every "
                "request will be rejected until a key is configured"
            )
        # --- materials: seed an empty store ----------------------------------
        #
        # Seeding here rather than in a migration keeps a fresh checkout
        # demonstrable on first start. It is explicitly SYNTHETIC DEMO data, every
        # record carries that status, and an already-populated database is left
        # untouched — so a restart never double-counts an inventory position.
        # The store itself was opened in the factory (the orchestrator needs it);
        # this block only decides whether it needs populating.
        try:
            if getattr(settings, "materials_seed", True) and materials_store.is_empty():
                from backend.materials.seed import seed_materials

                summary = seed_materials(materials_store)
                logger.info(
                    "materials seeded (SYNTHETIC DEMO): %s materials, %s price observations, "
                    "%s production records",
                    summary["materials"],
                    summary["price_observations"],
                    summary["production_records"],
                )
            else:
                logger.info("materials store ready: %s", materials_store.counts())
        except Exception as exc:  # noqa: BLE001 - a seed failure must not stop the API
            logger.error("materials store unavailable: %s", exc)

        # --- simulation: attach the service and boot a tick loop per dataset ---
        simulation_api.attach(simulation_service)
        sim_tasks = []
        if settings.simulation_enabled:
            import asyncio

            for meta in sim_datasets.list_plants():
                try:
                    simulation_service.register(sim_datasets.load_plant(meta["id"]))
                    simulation_service.ensure_loop(meta["id"], settings.simulation_tick_s)
                    logger.info("simulation registered: %s (%s assets)", meta["id"], meta["assets"])
                except Exception as exc:  # a broken dataset must not kill the API
                    logger.error("simulation dataset %s failed to load: %s", meta["id"], exc)

            # A plant saved from the Builder is registered at runtime, after this
            # loop ran. The supervisor keeps a tick loop on every registered
            # plant, so a built plant is driven exactly like a shipped dataset.
            async def _sim_loop_supervisor() -> None:
                while True:
                    try:
                        for pid in simulation_service.registered_ids():
                            simulation_service.ensure_loop(pid, settings.simulation_tick_s)
                    except Exception as exc:  # noqa: BLE001 - never kill the API
                        logger.error("simulation supervisor: %s", exc)
                    await asyncio.sleep(1.0)

            sim_tasks.append(asyncio.create_task(_sim_loop_supervisor()))
        yield
        for t in sim_tasks:
            t.cancel()
        # The tick loops are owned by the supervisor's registry rather than this
        # list, so cancel them explicitly on shutdown.
        for t in list(simulation_service._tick_tasks.values()):  # noqa: SLF001
            t.cancel()

    app = FastAPI(
        title="Project 117 Backend",
        version=__version__,
        description="Sovereign, local, agentic industrial AI for manufacturing operations.",
        lifespan=lifespan,
    )

    # --- services --------------------------------------------------------
    metrics = MetricsRegistry()
    audit_service = AuditService(session_factory, database_url=settings.database_url)
    model_roles = ModelRoles(settings)
    # Built before any provider: the policy is enforced *inside* the provider's
    # HTTP transport, so it has to exist first. Before Phase 0.5 this object
    # was constructed here and consulted by nothing.
    egress = policy_from_settings(settings)
    providers: dict[str, ModelProvider] = {
        settings.llm_backend: OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or None,
            timeout_seconds=settings.llm_timeout_seconds,
            egress=egress,
        )
    }
    gateway = ModelGateway(providers=providers, default_provider=settings.llm_backend)
    router = ModelRouter(gateway, model_roles, availability_ttl=settings.llm_availability_ttl)
    # Phase 4: hybrid retrieval + citations over the same LanceDB table the
    # ingestion pipeline fills. The retriever is lazy — nothing vendor-related
    # loads until the first search / chat-grounding call.
    retrieval = RetrievalService(
        retriever=LocalGPTRetriever(
            db_path=settings.lancedb_dir,
            table_name=settings.lancedb_table,
            embedding_model=settings.embedding_model,
            ollama_host=_ollama_api_host(settings.llm_base_url),
            reranker_model=settings.reranker_model,
        ),
        session_factory=session_factory,
        audit=audit_service,
        rerank_enabled=settings.retrieval_rerank_enabled,
        rerank_candidates=settings.retrieval_rerank_candidates,
    )
    sessions = ChatSessionStore()
    chat_service = ChatService(
        router,
        sessions,
        audit_service,
        retrieval=retrieval,
        default_use_rag=settings.chat_default_use_rag,
        evidence_top_k=settings.chat_evidence_top_k,
    )

    # Phase 9: the sandbox policy is built from settings and is the only
    # place an image, digest or resource limit can come from. It is not
    # validated (validate_ready) at startup — a deployment that never
    # executes code or generates artifacts must still be able to boot.
    sandbox_policy = sandbox_policy_from_settings(settings)
    sandbox_service = SandboxService(sandbox_policy)

    # Phase 6/8: approvals gate risky tool calls before they run.
    approval_policy = approval_policy_from_settings(settings)

    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Phase 2: artifacts are signed with Ed25519. The key is generated on first
    # use and persisted 0600 under the app's data directory (or at
    # P117_ARTIFACT_SIGNING_KEY). A key that cannot be loaded is a real
    # configuration error and is raised, not silently degraded — an
    # unauthenticated artifact must never be presented as a signed one.
    signing_key = load_or_create_key()

    # Phase 11: the verifier never gets a model router — see verifier.py.
    verifier = Verifier(sandbox=sandbox_service)

    # Phase 10: artifact lifecycle (spec -> sandbox -> sha256 -> verify -> store).
    # Phase 2 adds: -> Ed25519 signature, recorded on the artifact row.
    artifact_service = ArtifactService(
        sandbox=sandbox_service,
        storage_dir=settings.artifacts_dir,
        session_factory=session_factory,
        audit=audit_service,
        verifier=verifier,
        signing_key=signing_key,
    )

    # Phase 8: every tool call goes through this registry — schema, RBAC,
    # approval and limits enforced in that order (see tools/registry.py).
    tool_registry = build_default_registry(
        session_factory=session_factory,
        audit=audit_service,
        approval_policy=approval_policy,
        metrics=metrics,
    )

    # Phase 7: specialised agents, built through the registry so a disabled
    # agent degrades the answer instead of failing the job.
    agent_registry = build_agent_registry()

    # Phase 6: the orchestrator's managers. Each owns one decision (routing,
    # planning, context, execution, verification, recovery) so the
    # orchestrator itself only sequences them — see orchestrator/__init__.py.
    workflow_registry = load_registry(settings.workflows_dir)
    job_bus = JobEventBus()
    job_service = JobService(session_factory, bus=job_bus)
    task_router = TaskRouter(model_router=router, gateway=gateway)
    planner = Planner(model_router=router, gateway=gateway, tools=tool_registry)
    memory = MemoryService(session_factory, audit=audit_service)
    context_manager = ContextManager(retrieval=retrieval, memory=memory)
    agent_manager = AgentManager(
        agent_registry, model_router=router, gateway=gateway, tools=tool_registry
    )
    # The materials domain store is opened here rather than in the lifespan so it
    # exists before the orchestrator is built and can be handed to the agent's
    # tool context. Opening it is just "open SQLite and apply the schema" —
    # milliseconds. The slower part, seeding a fresh database, stays in the
    # lifespan where startup work belongs.
    materials_store = MaterialsStore(db_path=settings.materials_db)
    app.state.materials = materials_store

    # --- mobile field API -------------------------------------------------
    # The identity store backs real credential checks for the Android client.
    # It is opened and seeded here (not per request) so a fresh checkout can log
    # in immediately; the seeded accounts are flagged is_demo and announced.
    identity_store = IdentityStore(db_path=settings.identity_db)
    if settings.seed_demo_users:
        created = identity_store.seed_demo_accounts()
        if created:
            logger.warning(
                "identity store seeded with %s SYNTHETIC DEMO account(s) "
                "(technician, operator, supervisor, admin) — these are demo "
                "credentials, replace them before any shared deployment",
                created,
            )
    identity_store.seed_enrollment_codes(settings.enrollment_codes or DEFAULT_ENROLLMENT_CODES)
    # The mobile store holds the writes the phone makes; it opens the engine's
    # simulation database read-only to serve the real agent-task list.
    mobile_store = MobileStore(
        db_path=settings.mobile_db or default_mobile_db(),
        simulation_db=settings.simulation_db,
    )
    app.state.identity = identity_store
    app.state.mobile = mobile_store

    execution_manager = ExecutionManager(
        tools=tool_registry,
        agent_manager=agent_manager,
        context_manager=context_manager,
        session_factory=session_factory,
        audit=audit_service,
        retrieval=retrieval,
        sandbox=sandbox_service,
        artifacts=artifact_service,
        model_router=router,
        materials=materials_store,
    )
    verification_manager = VerificationManager(
        verifier=verifier, sandbox=sandbox_service, audit=audit_service
    )
    recovery_manager = RecoveryManager()
    workflow_manager = WorkflowManager(workflow_registry, tool_names=tool_registry.names())

    # Phase 6: the four execution policies. Built here so one deployment's
    # settings drive both the orchestrator and the direct tools API — a step
    # cannot dodge a gate by choosing a different entry point.
    action_policy = ActionPolicy(tools=tool_registry)
    tool_policy = tool_policy_from_settings(settings)
    plan_approval_policy = plan_approval_policy_from_settings(settings, tool_registry)

    orchestrator = Orchestrator(
        jobs=job_service,
        planner=planner,
        task_router=task_router,
        context_manager=context_manager,
        execution_manager=execution_manager,
        verification_manager=verification_manager,
        recovery_manager=recovery_manager,
        agent_manager=agent_manager,
        tools=tool_registry,
        workflow_manager=workflow_manager,
        retrieval=retrieval,
        sandbox=sandbox_service,
        artifacts=artifact_service,
        session_factory=session_factory,
        audit=audit_service,
        model_router=router,
        metrics=metrics,
        action_policy=action_policy,
        tool_policy=tool_policy,
        approval_policy=plan_approval_policy,
        egress=egress,
        max_chunks_per_step=settings.max_chunks_per_step,
    )

    app.state.settings = settings
    app.state.action_policy = action_policy
    app.state.tool_policy = tool_policy
    app.state.plan_approval_policy = plan_approval_policy
    app.state.session_factory = session_factory
    app.state.metrics = metrics
    app.state.audit = audit_service
    # The egress path cannot import the API (the httpx transport imports the
    # monitor on a hot path), so the durable audit sink is handed to it here.
    # Without this the sentinel streams and counts a decision but the Security
    # Events panel never sees it.
    register_audit_sink(audit_service)
    app.state.memory = memory
    app.state.tracing = AgentTraceRecorder()
    app.state.egress = egress
    app.state.model_roles = model_roles
    app.state.gateway = gateway
    app.state.router = router
    app.state.sessions = sessions
    app.state.chat = chat_service
    app.state.agents = agent_registry
    app.state.workflows = workflow_registry
    app.state.retrieval = retrieval
    app.state.sandbox_policy = sandbox_policy
    app.state.sandbox = sandbox_service
    app.state.approval_policy = approval_policy
    app.state.tools = tool_registry
    app.state.artifacts = artifact_service
    app.state.verifier = verifier
    app.state.jobs = job_service
    app.state.job_bus = job_bus
    app.state.orchestrator = orchestrator
    app.state.documents = DocumentStorage(
        session_factory=session_factory,
        uploads_dir=settings.uploads_dir,
        allowed_extensions=settings.allowed_extensions,
        max_upload_bytes=settings.max_upload_bytes,
        audit=audit_service,
    )
    app.state.ingestion = IngestionService(
        session_factory=session_factory,
        stager=DocumentStager(settings.uploads_dir / "staging"),
        indexer=LocalGPTIndexer(
            db_path=settings.lancedb_dir,
            table_name=settings.lancedb_table,
            chunk_size=settings.chunk_size_tokens,
            chunk_overlap=settings.chunk_overlap_sentences,
            embedding_model=settings.embedding_model,
            ollama_host=_ollama_api_host(settings.llm_base_url),
        ),
        audit=audit_service,
        ingestible_extensions=settings.ingestible_extensions,
        uploads_dir=settings.uploads_dir,
    )

    # Browser workbench access. The CORSMiddleware answers preflight (OPTIONS)
    # requests and stamps real responses — without it the browser blocks every
    # cross-origin fetch/SSE stream with a CORS error, even though curl works.
    # Added FIRST so it wraps every other layer (Starlette runs last-added
    # first) and preflights never touch auth/permissions/audit.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # --- middleware ------------------------------------------------------
    # Starlette wraps each newly added layer *around* the previous one, so the
    # last one added runs first. Added innermost-first below; the effective
    # request path is:
    #   principal -> audit -> rate limit -> permissions -> metrics -> route
    app.add_middleware(RequestMetricsMiddleware, metrics=metrics)
    app.add_middleware(RoutePermissionMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
        workers=settings.workers,
    )
    app.add_middleware(RequestAuditMiddleware)
    app.add_middleware(PrincipalMiddleware)

    # --- routes ----------------------------------------------------------
    app.include_router(health.router)  # GET /health (no prefix)
    app.include_router(models.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(knowledge.router)
    app.include_router(auth.router)
    app.include_router(equipment.router)
    app.include_router(work_orders.router)
    app.include_router(approvals.router)
    app.include_router(analytics.router)
    app.include_router(agents.router)
    app.include_router(jobs.router)
    app.include_router(workflows.router)
    app.include_router(tools.router)
    app.include_router(artifacts.router)
    app.include_router(audit.router)
    app.include_router(network.router)
    app.include_router(sovereignty.router)
    app.include_router(simulation_api.router)
    app.include_router(materials.router)
    # The Android field client's surface: base URL http://<host>:8000/api/v1/.
    app.include_router(mobile.router)

    @app.get("/api/metrics")
    def api_metrics(request: Request) -> dict:
        return request.app.state.metrics.snapshot()

    @app.get("/")
    def root() -> dict:
        return {
            "service": "project-117-backend",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
        }

    # --- error handling --------------------------------------------------
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.payload())

    @app.exception_handler(EndpointNotImplemented)
    async def handle_not_implemented(request: Request, exc: EndpointNotImplemented) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.payload())

    @app.exception_handler(AuthenticationError)
    async def handle_unauthenticated(request: Request, exc: AuthenticationError) -> JSONResponse:
        # Raised from a dependency (deps.get_principal). Without this handler a
        # bad credential surfaced as a 500 instead of a 401.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.reason, "message": exc.message}},
            headers={"WWW-Authenticate": "X-P117-Api-Key"},
        )

    @app.exception_handler(AuthorizationError)
    async def handle_forbidden(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.reason,
                    "message": str(exc),
                    "permission": exc.permission,
                }
            },
        )

    @app.exception_handler(DocumentValidationError)
    async def handle_document_validation(request: Request, exc: DocumentValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "bad_request", "message": str(exc)}},
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        # Covers ModelRouter.resolve's unknown-role ValueError and any other
        # programmer-facing validation that leaks to the boundary.
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": str(exc)}},
        )

    @app.exception_handler(IngestionError)
    async def handle_ingestion_error(request: Request, exc: IngestionError) -> JSONResponse:
        status = 415 if isinstance(exc, UnsupportedForIngestion) else 422
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": exc.reason,
                    "message": str(exc),
                    "phase": 3,
                }
            },
        )

    @app.exception_handler(ToolError)
    async def handle_tool_error(request: Request, exc: ToolError) -> JSONResponse:
        # ToolError derives from RuntimeError, so before this handler every
        # tool fault fell through to FastAPI's default and surfaced as a 500:
        # a caller passing bad arguments (`POST /api/tools/execute`), asking
        # for a tool that does not exist, or hitting a tool that needs human
        # approval all looked like a server crash. None of those are server
        # faults, so each now maps to its own status.
        status = 500
        if isinstance(exc, ToolNotFound):
            status = 404
        elif isinstance(exc, ToolArgumentError):
            status = 400
        elif isinstance(exc, ToolPermissionDenied):
            status = 403
        elif isinstance(exc, ToolApprovalRequired):
            status = 409
        elif isinstance(exc, ToolTimeout):
            status = 504
        elif isinstance(exc, ToolUnavailable):
            status = 503
        error: dict = {"code": exc.reason, "message": str(exc)}
        if isinstance(exc, ToolApprovalRequired):
            # The client needs to know which tool and how risky it is to be
            # able to route the request into the job approval flow.
            error["tool"] = exc.tool
            error["risk"] = exc.risk
        return JSONResponse(status_code=status, content={"error": error})

    @app.exception_handler(RetrievalError)
    async def handle_retrieval_error(request: Request, exc: RetrievalError) -> JSONResponse:
        from backend.api.src.routes.knowledge import retrieval_error_status

        return JSONResponse(
            status_code=retrieval_error_status(exc),
            content={
                "error": {
                    "code": exc.reason,
                    "message": str(exc),
                    "phase": 4,
                }
            },
        )

    return app
