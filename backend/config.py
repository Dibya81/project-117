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
# ``P117_SIM_RETRIEVAL*``, ``P117_FILE_ROOTS``, ``P117_WORKSPACE_DIR``,
# ``P117_DEMO_*`` — and pydantic-settings does not export ``.env`` entries into
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

    # An Ollama tag is "name:tag" and runs locally; a Hugging Face repo id is
    # "org/name" and downloads weights. Any role containing "/" is rejected at
    # startup unless this is deliberately set true.
    allow_remote_model_repos: bool = False
    # Simulation (digital twin) — datasets under data/simulation; the tick loop
    # only runs when datasets are present (scripts/generate_simulation_data.py).
    simulation_enabled: bool = True
    simulation_tick_s: float = 1.0

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
    ingestible_extensions: set[str] = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}

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

    # --- observability ---------------------------------------------------
    # JSON logs are always written to stdout; set json_logs=false for
    # human-readable console output.
    json_logs: bool = False

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

    def unconfigured_roles(self) -> list[str]:
        """Roles with no model configured, in canonical order.

        Logged once at startup so an operator learns what is missing before a
        request fails, rather than after.
        """
        return [role for role, field in _ROLE_FIELDS if not getattr(self, field)]
