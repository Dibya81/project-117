"""Application configuration.

Every setting is overridable from the environment using the ``P117_`` prefix
(see the root ``.env.example``). Model names are configuration, never
hard-coded in application code — Phases 2+ route through the model gateway
using these role names.

Phase 0.5 made this module fail closed: no model role has a default, and a
Hugging Face repo id is rejected at startup rather than downloaded on first
use. See docs/decisions/0003-phase-0.5-hardening.md.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the repo-root ``.env`` into the process environment, *without*
# overriding variables that are already exported.
#
# ``BaseSettings(env_file=".env")`` below only ever fed the fields declared on
# ``Settings``. Several settings are read straight from ``os.environ`` instead
# — ``P117_AUDIT_HTTP``, ``P117_RATE_LIMIT_*``, ``P117_SIMULATION_DB``,
# ``P117_SIM_RETRIEVAL*``, ``P117_FILE_ROOTS``, ``P117_WORKSPACE_DIR`` — and pydantic-settings does not export ``.env`` entries into
# the environment. Nothing else called ``load_dotenv`` either, so documenting
# those variables in ``.env`` had no effect at all: the value was silently
# ignored, which is indistinguishable from the feature being broken.
#
# ``override=False`` keeps the conventional precedence — a real exported
# variable always beats the file. The path is CWD-relative, which is why the
# backend is documented to run from the repository root.
load_dotenv(Path(".env"), override=False)

# Deliberately module-level rather than a class attribute: pydantic-settings
# reserves underscore-prefixed class attributes and would reject it.
_ROLE_FIELDS = (
    ("reasoning", "reasoning_model"),
    ("vision", "vision_model"),
    ("embedding", "embedding_model"),
    ("reranker", "reranker_model"),
    ("coding", "coding_model"),
    ("domain", "domain_model"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="P117_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- service ---------------------------------------------------------
    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    workers: int = 1
    rate_limit_per_minute: int = 0
    rate_limit_burst: int | None = None

    # --- persistence -----------------------------------------------------
    # SQLite is the Phase-1 default (zero infrastructure). Postgres arrives
    # with the Phase-17 persistence work: postgresql+psycopg://user:pw@host/db
    database_url: str = "sqlite:///./data/project117.db"

    # --- browser access ----------------------------------------------------
    # The Next.js workbench (default http://127.0.0.1:3017) talks to this API
    # from the browser, so cross-origin requests must be answered with CORS
    # headers. Same-origin deployments need no change; multi-origin setups add
    # entries here (P117_CORS_ORIGINS, comma-separated).
    cors_origins: set[str] = {
        "http://127.0.0.1:3017",
        "http://localhost:3017",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    }

    # --- document storage ------------------------------------------------
    uploads_dir: Path = Path("./data/uploads")

    # --- workflows ---------------------------------------------------------
    # Directory of YAML workflow definitions, loaded once at startup. Missing
    # is fine (empty registry); malformed files are skipped with a warning,
    # never silently dropped without a log line.
    #
    # Repo-root-relative, matching the documented run command (`uv run uvicorn
    # backend.api.src.main:create_app` from the repository root). The previous
    # default was `../workflows/definitions`, which resolves *outside* the
    # checkout from that CWD, so a fresh clone with no .env silently started
    # with an empty workflow registry.
    workflows_dir: Path = Path("workflows/definitions")
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 MB
    allowed_extensions: set[str] = {
        ".pdf",
        ".docx",
        ".doc",
        ".txt",
        ".md",
        ".html",
        ".htm",
        # Presentation and spreadsheet formats: the committed refinery corpus
        # includes both, and Docling converts them natively.
        ".pptx",
        ".xlsx",
        ".png",
        ".jpg",
        ".jpeg",
    }

    # --- local model endpoints -------------------------------------------
    # The model gateway talks to one OpenAI-compatible endpoint. Ollama's
    # /v1 (default below) and vLLM both speak this protocol; switching is a
    # config change, never a code change.
    llm_backend: str = "openai_compatible"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 120.0
    #: Context window requested per agent call (``num_ctx``). Ollama's default is
    #: small, and a small reasoning model can spend its entire budget on hidden
    #: chain-of-thought — which truncates the reply before any content is
    #: emitted. A generous window plus an output budget above the reasoning
    #: reserve is what makes a structured-JSON reply actually arrive.
    llm_num_ctx: int = 4096
    #: Whether to let a reasoning model emit its hidden chain-of-thought.
    #:
    #: Defaults to ``off``. Every caller of the structured simulation agents asks
    #: for strict JSON, and the trace is charged against the output budget while
    #: not being part of ``message.content`` — so leaving it on meant qwen3:1.7b
    #: spent the entire budget thinking and returned an EMPTY reply, on every
    #: call. This was previously read as ``getattr(settings, "llm_think", "")``,
    #: which does not exist on Settings, so the flag was never sent at all.
    #: Set it to ``on`` only for a caller that wants the reasoning text.
    llm_think: str = "off"
    # How long the router caches the provider's model list before re-checking.
    llm_availability_ttl: float = 60.0
    open_sandbox_base_url: str = "http://localhost:8080"

    # --- model roles (Phase 2 — model gateway) ---------------------------
    # FAIL CLOSED. Every role is unconfigured by default: nothing is assumed
    # and nothing is downloaded. Asking for an unconfigured role returns a
    # clear configuration error (503 model_unavailable) naming the variable to
    # set — it never silently picks a model.
    #
    # The previous defaults (qwen3.5:9b / qwen3.5:4b / Qwen/Qwen3-Reranker-4B)
    # contradicted .env.example, which showed an unconfigured state, and could
    # trigger a multi-GB Hugging Face download on the first request — from a
    # system whose entire claim is that nothing leaves the machine.
    reasoning_model: str = ""
    vision_model: str = ""
    embedding_model: str = ""
    reranker_model: str = ""
    coding_model: str = ""
    domain_model: str = ""
    # Optional override for the simulation's three-agent recovery decision
    # (Diagnostic / Operations / Safety). Unset, each agent keeps its role model
    # above. A single small local model for all three turns keeps the incident
    # decision quick and consistent, without changing the models the rest of the
    # application uses.
    decision_model: str = ""

    # Per-agent model overrides for the three simulation decision agents.
    # When set, each agent uses its own dedicated model regardless of
    # decision_model or the role-based reasoning/domain assignments above.
    # This enables heterogeneous models per role (e.g. qwen3:1.7b for
    # diagnostics, llama3.2:3b for operations, gemma3:1b for safety).
    #   P117_DIAGNOSTIC_MODEL=qwen3:1.7b
    #   P117_OPERATIONS_MODEL=llama3.2:3b
    #   P117_SAFETY_MODEL=gemma3:1b
    diagnostic_model: str = ""
    operations_model: str = ""
    safety_model: str = ""

    # Reply budget for one simulation decision agent turn.
    #
    # Sized for the reasoning models in the roster: ``qwen3:1.7b`` spends ~400
    # tokens on hidden reasoning that is counted against this budget but is not
    # returned as content, so a budget sized only for the JSON answer (400)
    # truncated the Diagnostic agent to an empty reply on every call and no
    # incident could ever be decided. Lower it only for non-reasoning models.
    #: 2048, not 1024. With the reasoning trace suppressed a diagnostic turn
    #: costs ~330 tokens (measured), so 1024 is plenty — but a local server that
    #: ignores ``think:false`` spends ~400 tokens thinking before it emits
    #: anything, and truncates to an EMPTY reply at 1024. The budget is a ceiling,
    #: not a cost, so the headroom is free.
    decision_max_tokens: int = 2048

    # An Ollama tag is "name:tag" and runs locally; a Hugging Face repo id is
    # "org/name" and downloads weights. Any role containing "/" is rejected at
    # startup unless this is deliberately set true.
    allow_remote_model_repos: bool = False
    # Simulation (digital twin) — plants live in the simulation SQLite store,
    # seeded on first run from project-117-simulation/database/seed_plants.sql;
    # the tick loop only runs when plants are registered.
    simulation_enabled: bool = True
    simulation_tick_s: float = 1.0
    #: Persist telemetry to SQLite every Nth tick. 1 restores the historical
    #: behaviour of writing on every tick; the default is lower because nothing
    #: currently reads the table, and the per-tick commit contended with the
    #: incident/task/audit writes the live console depends on. Telemetry itself
    #: still streams to the console at full rate over ``telemetry.batch``.
    telemetry_every: int = 15

    # Operations surfaces (equipment / work orders / approvals / analytics).
    # Equipment is read from the real plant dataset in the simulation store
    # above; runtime work orders and approval decisions are persisted in this
    # local SQLite file. ``operations_plant`` is the default plant served when
    # the caller does not pass ``?plant=`` — the other dataset stays reachable.
    operations_db: Path = Path("./data/operations.db")
    operations_plant: str = "refinery"

    # --- industrial materials / inventory / business intelligence ---------
    # One SQLite file for the whole materials domain (materials, balances,
    # movements, production, price history, requirements, suppliers, financial
    # events). Seeded on first start with coherent SYNTHETIC DEMO data that is
    # linked to the real plant dataset — every record it writes is marked
    # ``SYNTHETIC_DEMO`` and says so in the API response.
    materials_db: Path = Path("./data/materials.db")
    materials_seed: bool = True

    # --- document ingestion (Phase 3 — localGPT adapter) -----------------
    # LanceDB directory holding vector + FTS indexes. One table per backend
    # process; chunk rows carry full citation metadata (document_id, page,
    # heading_path, chunk_index).
    lancedb_dir: Path = Path("./data/lancedb")
    lancedb_table: str = "p117_chunks"
    # Token budget per chunk (localGPT chunkers are token-based).
    chunk_size_tokens: int = 1500
    chunk_overlap_sentences: int = 1
    # Extensions eligible for indexing (superset allowed for upload).
    # Formats the ingestion pipeline (Docling + localGPT) can actually convert.
    # 3 of the 8 committed refinery corpus documents are PPTX/XLSX, so leaving
    # them out meant a quarter of the real corpus was rejected at upload.
    ingestible_extensions: set[str] = {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".txt",
        ".md",
        ".html",
        ".htm",
    }

    # --- hybrid retrieval (Phase 4 — localGPT adapter) -------------------
    # Reranking re-scores the fused candidate list with the configured
    # reranker model (P117_RERANKER_MODEL). OFF by default: every reranker
    # backend we vendor resolves to a Hugging Face download, so defaulting it
    # on contradicted the sovereignty posture. Enable deliberately with
    # `uv sync --extra rerank` plus locally present reranker weights.
    retrieval_rerank_enabled: bool = False
    # How many fused candidates the reranker sees before cutting to top_k.
    retrieval_rerank_candidates: int = 30
    # Evidence chunks attached to a document-grounded chat turn.
    chat_evidence_top_k: int = 5
    # Serve chat turns grounded by default (clients can override per request).
    chat_default_use_rag: bool = False

    # --- security --------------------------------------------------------
    # Enforced in the HTTP transport layer (backend/security/egress.py), not
    # merely declared: every outbound request is checked before it leaves.
    egress_default_deny: bool = True
    # Exact hostnames, comma-separated. No wildcards — a wildcard allowlist is
    # how zero-egress quietly becomes full egress. localhost / 127.0.0.1 / ::1
    # are always permitted so local model servers and OpenSandbox work.
    egress_allowed_hosts: set[str] = set()

    # --- sandbox (Phase 9) ------------------------------------------------
    # Overrides for backend.sandbox.policy.SandboxPolicy. Leave images/digests
    # empty to use the built-in defaults; an unknown attribute never widens
    # the sandbox (see policy_from_settings).
    sandbox_image: str = ""
    sandbox_documents_image: str = ""
    sandbox_image_digest: str = ""
    sandbox_documents_image_digest: str = ""
    sandbox_api_key: str = ""
    sandbox_require_api_key: bool = True
    sandbox_cpu_millicores: int = 500
    sandbox_memory_mib: int = 512
    sandbox_timeout_seconds: int = 120
    sandbox_lifetime_seconds: int = 600
    sandbox_max_output_bytes: int = 256_000
    sandbox_max_artifact_bytes: int = 25 * 1024 * 1024
    sandbox_allow_network: bool = False

    # --- artifacts (Phase 10) ---------------------------------------------
    artifacts_dir: Path = Path("./data/artifacts")

    # --- approvals (Phase 6 policy, Phase 12 wiring) ----------------------
    # Comma-separated tool names always requiring approval, on top of the
    # execute/external risk-level gate.
    approval_always_require: set[str] = set()
    approval_auto_execute: bool = False
    approval_auto_external: bool = False

    # --- tool policy (Phase 6) --------------------------------------------
    # Deployment reach, which is a different question from "does the caller
    # hold the permission" (rbac) and "does a human need to sign off"
    # (approvals). A site may allow an operator to hold code:execute while
    # still refusing to run execute-risk tools here.
    # Highest risk this deployment runs at all: read|compute|write|execute|external.
    tool_max_risk: str = "execute"
    # Comma-separated. A non-empty allowlist is exclusive.
    tool_allowlist: set[str] = set()
    tool_denylist: set[str] = set()
    # Ceiling on tool invocations in a single job, so a looping plan cannot
    # spend the machine.
    tool_max_calls_per_plan: int = 32
    # Ceiling on evidence chunks any one step may pull into model context.
    max_chunks_per_step: int = 24

    # --- auth (Phase 12) --------------------------------------------------
    # Off by default for a single-user on-premise install (see security/rbac.py
    # for what an anonymous caller may do). Turn on for any deployment that is
    # reachable from more than one workstation.
    auth_required: bool = False
    auth_api_key: str = ""
    # Roles granted to any request that presents a valid X-P117-Api-Key.
    # The client-supplied X-P117-Roles header is IGNORED for authenticated
    # callers — roles are bound to the credential server-side, not declared by
    # the request. Comma-separated. Defaults to a single 'operator' role.
    # Set P117_AUTH_ROLES=admin to grant full admin access to the API key holder.
    #
    # SECURITY NOTE: this is what prevents authenticated callers from self-
    # escalating by setting X-P117-Roles: admin. Anonymous callers are already
    # capped by ANONYMOUS_MAX_ROLES; this setting closes the same gap for
    # authenticated callers.
    auth_roles: tuple[str, ...] = ("operator",)

    # --- mobile field API (Phase 12 extension) ----------------------------
    # The Android client authenticates people, not machines, so it needs its
    # own persistent identity, a place for the runtime records it writes, and a
    # signing secret for its bearer tokens. See backend/storage/identity.py,
    # backend/storage/mobile.py and backend/security/mobile_auth.py.
    identity_db: Path = Path("./data/identity.db")
    mobile_db: Path = Path("./data/mobile.db")
    #: Mirrors P117_SIMULATION_DB, which the engine reads directly. The mobile
    #: store opens it read-only to serve the agent task list.
    simulation_db: Path = Path("./data/simulation.db")
    #: Leave unset and a random secret is generated once and stored in the
    #: identity database, so tokens survive a restart. Set it explicitly to
    #: manage rotation; a value shorter than 16 characters is refused.
    mobile_token_secret: str = ""
    mobile_access_ttl_seconds: int = 30 * 60
    mobile_refresh_ttl_seconds: int = 30 * 24 * 60 * 60
    #: Seed the one-per-role SYNTHETIC DEMO accounts into an empty identity
    #: store. They are flagged is_demo and logged at startup.
    seed_demo_users: bool = True
    #: Shared device-enrolment codes. Empty means the built-in demo codes
    #: (ENROLL-2026-*) are installed instead.
    enrollment_codes: set[str] = set()

    # --- observability ---------------------------------------------------
    # JSON logs are always written to stdout; set json_logs=false for
    # human-readable console output.
    json_logs: bool = False

    @field_validator("auth_roles", mode="before")
    @classmethod
    def _parse_auth_roles(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(r.strip().lower() for r in value.split(",") if r.strip())
        if isinstance(value, (list, tuple, set, frozenset)):
            return tuple(str(r).strip().lower() for r in value if str(r).strip())
        return value

    @field_validator(
        "allowed_extensions",
        "ingestible_extensions",
        "approval_always_require",
        "tool_allowlist",
        "tool_denylist",
        "cors_origins",
        mode="before",
    )
    @classmethod
    def _parse_extensions(cls, value: object) -> object:
        if isinstance(value, str):
            return {ext.strip().lower() for ext in value.split(",") if ext.strip()}
        return value

    @field_validator("egress_allowed_hosts", mode="before")
    @classmethod
    def _parse_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return {host.strip().lower() for host in value.split(",") if host.strip()}
        return value

    @field_validator("enrollment_codes", mode="before")
    @classmethod
    def _parse_enrollment_codes(cls, value: object) -> object:
        # Case is preserved: an enrolment code is a credential presented
        # verbatim by the handset, not a case-insensitive extension.
        if isinstance(value, str):
            return {code.strip() for code in value.split(",") if code.strip()}
        return value

    @model_validator(mode="after")
    def _reject_remote_model_repos(self) -> "Settings":
        # Failing at startup beats failing halfway through a user's request,
        # and beats silently pulling weights off the public internet.
        if self.allow_remote_model_repos:
            return self
        offenders = [
            f"{field}={getattr(self, field)!r}"
            for _, field in _ROLE_FIELDS
            if "/" in (getattr(self, field) or "")
        ]
        if offenders:
            raise ValueError(
                "model role(s) point at a remote model repository, which would "
                "download weights and break the zero-egress guarantee: "
                + ", ".join(offenders)
                + ". Use a locally served tag (e.g. 'qwen3:8b'), or set "
                "P117_ALLOW_REMOTE_MODEL_REPOS=true if this machine is "
                "deliberately not air-gapped."
            )
        return self

    @model_validator(mode="after")
    def _validate_rate_limiting_workers(self) -> "Settings":
        if self.workers > 1 and self.rate_limit_per_minute > 0:
            raise ValueError(
                f"Multi-worker configuration (P117_WORKERS={self.workers}) with "
                f"in-process rate limiting (P117_RATE_LIMIT_PER_MINUTE={self.rate_limit_per_minute}) "
                "is unsupported. In-process token buckets do not share state across workers. "
                "Either set P117_RATE_LIMIT_PER_MINUTE=0 or deploy with a single worker (P117_WORKERS=1)."
            )
        return self

    def unconfigured_roles(self) -> list[str]:
        """Roles with no model configured, in canonical order.

        Logged once at startup so an operator learns what is missing before a
        request fails, rather than after.
        """
        return [role for role, field in _ROLE_FIELDS if not getattr(self, field)]
