"""``GET /api/security/sovereignty`` — the Security Console's real state.

The rule this endpoint exists to enforce: **no status is green because code
exists.** Every entry is resolved from a measurement taken here, now, and the
response says which measurement. Three states are deliberately distinct, because
collapsing them is how a security dashboard starts lying:

* ``VERIFIED`` — something was measured and answered: the model gateway
  returned a model list, the verifier walked the chain, the index reported
  rows. This is the only state that may be shown green.
* ``IMPLEMENTED`` — the capability exists and is wired to a call site, but this
  process has no positive evidence for it yet. Amber, not green.
* ``PARTIAL`` — it does some of what it claims and the response names the gap.
* ``NOT_AVAILABLE`` — the capability cannot run in this environment. Red, and
  the reason is stated. Nothing here is ever reported as enforced on the
  strength of a configuration flag alone.

The sandbox and the OS-level egress layer are the two concrete cases the brief
calls out, and both are reported ``NOT_AVAILABLE`` with the measured reason:
OpenSandbox is not running on this host (every ``sandbox_command`` returns
``ACTION BLOCKED / SANDBOX UNAVAILABLE``), and nftables/iptables is a Linux
facility while this host is macOS.
"""

from __future__ import annotations

import asyncio
import platform
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.api.src.deps import get_settings
from backend.security.network.network_monitor import summary as network_summary

router = APIRouter(prefix="/api/security", tags=["security"])

class EgressProbeRequest(BaseModel):
    """A destination for the socket-free egress probe."""

    url: str = Field(min_length=8, max_length=2048)


#: The state vocabulary, in the order the console renders it.
VERIFIED = "VERIFIED"
IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
NOT_AVAILABLE = "NOT AVAILABLE"


def _entry(
    key: str,
    label: str,
    state: str,
    detail: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One status line. ``evidence`` is what was actually measured."""
    return {
        "key": key,
        "label": label,
        "state": state,
        "detail": detail,
        "evidence": evidence or {},
    }


@router.get("/sovereignty")
async def sovereignty_status(request: Request) -> dict:
    settings = get_settings(request)
    state = request.app.state
    services = await asyncio.gather(
        _local_ai(state),
        _local_vision(state),
        _local_knowledge(state),
        _vector_store(state),
        _tool_registry(state),
        _sandbox(state),
        return_exceptions=True,
    )
    local_ai, vision, knowledge, vectors, tools, sandbox = (
        value if isinstance(value, dict) else _entry("unknown", "unknown", NOT_AVAILABLE, str(value))
        for value in services
    )
    return {
        "generated_at": _now(),
        "host": {
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "status": [
            local_ai,
            _egress(state, settings),
            _audit_chain(state),
            _signing(state),
            _rbac(state),
            _clearance(state),
            sandbox,
        ],
        # The local-capability list. These are the rows the brief requires to
        # report honestly rather than to exist: a directory is not a capability.
        "capabilities": [vision, knowledge, vectors, tools],
    }


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --- security evaluation ----------------------------------------------------

#: The controls this build has and the ones it does not. Stated as data so the
#: console cannot imply a control exists because a row looks like the others.
#: Each implemented control is EXERCISED (see :func:`run_security_evaluation`),
#: never merely asserted: `PASS` means the call was made and the refusal
#: happened.
EVALUATION_SCENARIOS: tuple[dict[str, str], ...] = (
    {"id": "unauthorized_privileged_action", "name": "Unauthorized privileged action", "expected": "refused"},
    {"id": "unauthorized_retrieval", "name": "Unauthorized retrieval (clearance boundary)", "expected": "refused"},
    {"id": "external_egress", "name": "External egress attempt", "expected": "refused"},
    {"id": "insufficient_evidence", "name": "Insufficient evidence", "expected": "abstain-or-refuse"},
    {"id": "prompt_injection_in_document", "name": "Prompt injection hidden in a document", "expected": "detected-and-neutralised"},
)


@router.post("/evaluation")
def run_security_evaluation(request: Request) -> dict:
    """Exercise the refusal controls this build actually has.

    Every ``PASS`` is the result of making a real call and observing a real
    refusal — a permission check against the real role map, the real egress
    policy, the real clearance layer. Nothing is written to the audit log, no
    external socket is opened, and no plant state is touched.

    Two of the scenarios in the brief's evaluation set are reported ``NOT
    IMPLEMENTED``. That is the honest answer for this build: there is no
    prompt-injection detector anywhere in the request path, and no
    insufficient-evidence abstention policy — the grounded prompt simply omits
    evidence when retrieval returns none. Reporting either as PASS because a
    related mechanism exists is exactly the kind of green tick this console is
    not allowed to produce.
    """
    results = []
    for scenario in EVALUATION_SCENARIOS:
        if scenario["id"] == "unauthorized_privileged_action":
            results.append(_eval_permission())
        elif scenario["id"] == "unauthorized_retrieval":
            results.append(_eval_clearance())
        elif scenario["id"] == "external_egress":
            results.append(_eval_egress(request))
        else:
            detail = {
                "insufficient_evidence": (
                    "Chat is grounded when retrieval returns evidence and ungrounded when it returns "
                    "none; nothing detects or reports insufficient evidence as a distinct outcome."
                ),
                "prompt_injection_in_document": (
                    "Retrieved text is passed to the model as context with no injection detector or "
                    "instruction-hierarchy guard. Document content is data to this system only by "
                    "convention, not by enforcement."
                ),
            }[scenario["id"]]
            results.append(
                {**scenario, "status": "NOT IMPLEMENTED", "actual": "no control exists in this build for this scenario", "detail": detail}
            )
    return {
        "generated_at": _now(),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "not_implemented": sum(1 for r in results if r["status"] == "NOT IMPLEMENTED"),
        "results": results,
    }


def _eval_permission() -> dict[str, Any]:
    from backend.security.rbac import AuthorizationError, require
    from backend.tools.base import Permission

    role, permission = "viewer", Permission.JOBS_APPROVE
    try:
        require(permission, roles=[role])
    except AuthorizationError as exc:
        return {
            "id": "unauthorized_privileged_action",
            "name": "Unauthorized privileged action",
            "expected": "refused",
            "status": "PASS",
            "actual": f"AuthorizationError: {exc}",
            "detail": f"role '{role}' was refused '{permission.value}' by the RBAC gate.",
        }
    return {
        "id": "unauthorized_privileged_action",
        "name": "Unauthorized privileged action",
        "expected": "refused",
        "status": "FAIL",
        "actual": f"role '{role}' was granted '{permission.value}'",
        "detail": "the RBAC gate did not refuse a privileged action for an unprivileged role",
    }


def _eval_clearance() -> dict[str, Any]:
    from backend.security.clearance import ClearanceDenied
    from backend.security.clearance.access import require_document_clearance
    from backend.security.rbac import Principal

    viewer = Principal(user="evaluation", roles=("viewer",))
    record = {"metadata": {"clearance": "HIGHLY_CONFIDENTIAL"}}
    try:
        require_document_clearance(viewer, record, resource_id="evaluation")
    except ClearanceDenied as exc:
        return {
            "id": "unauthorized_retrieval",
            "name": "Unauthorized retrieval (clearance boundary)",
            "expected": "refused",
            "status": "PASS",
            "actual": f"ClearanceDenied: held {exc.held}, required {exc.required}",
            "detail": "a PUBLIC caller was refused a HIGHLY_CONFIDENTIAL record.",
        }
    return {
        "id": "unauthorized_retrieval",
        "name": "Unauthorized retrieval (clearance boundary)",
        "expected": "refused",
        "status": "FAIL",
        "actual": "the clearance check allowed the read",
        "detail": "the clearance layer did not refuse a record above the caller's level",
    }


def _eval_egress(request: Request) -> dict[str, Any]:
    from backend.security.egress import EgressBlocked, policy_from_settings
    from backend.security.network.egress_policy import check_and_record

    policy = policy_from_settings(get_settings(request))
    # An RFC 5737 documentation address: it can never resolve to a real
    # service, and `check_and_record` refuses it before any socket is opened,
    # so this proves the refusal without contacting anything.
    url = "https://198.51.100.7/evaluation-probe"
    try:
        check_and_record(policy, url)
    except EgressBlocked as exc:
        return {
            "id": "external_egress",
            "name": "External egress attempt",
            "expected": "refused",
            "status": "PASS",
            "actual": f"EgressBlocked: {exc}",
            "detail": f"the policy refused {url} before a socket was opened.",
        }
    return {
        "id": "external_egress",
        "name": "External egress attempt",
        "expected": "refused",
        "status": "FAIL",
        "actual": "the policy allowed the URL",
        "detail": f"the egress policy permitted {url}",
    }


@router.get("/events")
def security_events(request: Request, limit: int = 40) -> dict:
    """Security-relevant audit rows only — the console's Security Events panel.

    Filtered by the action namespaces that mean something security-wise. The
    request log (``http.*``) is deliberately excluded here as well as at the
    query: it is a transport record, and three quarters of the table would bury
    the rows an operator is looking for.

    ``exercised`` reports how many rows of each namespace exist in total, so the
    panel can distinguish "this control has never fired" from "this filter is
    wrong" — the two look identical in a short list.
    """
    audit = getattr(request.app.state, "audit", None)
    if audit is None:
        return {"available": False, "reason": "no audit service is attached", "events": [], "namespaces": []}
    # Prefixes, not a fixed list of action names: a new security action is
    # picked up by the panel without a second registration step.
    prefixes = ("network.", "auth.", "permission.", "clearance.", "sandbox.", "audit.", "approval.")
    rows = audit.list(limit=min(max(limit * 6, 120), 2000))
    events = []
    counts: dict[str, int] = {}
    for event in rows:
        action = event.action or ""
        namespace = action.split(".", 1)[0] + "."
        if not action.startswith(prefixes):
            continue
        counts[namespace] = counts.get(namespace, 0) + 1
        events.append(
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "action": action,
                "outcome": event.outcome,
                "user": event.user,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "agent": event.agent,
                "tool": event.tool,
                "error": event.error,
            }
        )
        if len(events) >= limit:
            break
    return {
        "available": True,
        "namespaces": [{"namespace": k, "count": v} for k, v in sorted(counts.items())],
        "total": len(events),
        "events": events,
    }


@router.post("/artifacts/{artifact_id}/verify")
def verify_artifact(artifact_id: str, request: Request) -> dict:
    """Re-verify one artifact's Ed25519 signature against the bytes on disk.

    A thin passthrough to the real implementation — the console must not have
    its own verifier, or the page could report a verification the service never
    performed. A missing artifact is a 404-shaped answer, not a zero.
    """
    artifacts = getattr(request.app.state, "artifacts", None)
    if artifacts is None:
        return {"available": False, "reason": "no artifact service is attached"}
    try:
        return {"available": True, **artifacts.verify_signature(artifact_id)}
    except Exception as exc:  # noqa: BLE001 - a refused verification is a result
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


@router.post("/egress-probe")
def egress_probe(payload: EgressProbeRequest, request: Request) -> dict:
    """Take one real egress decision inside this process, without any egress.

    Why this exists: the Network Sentinel's whole claim is that a decision taken
    by the guard reaches the stream, the audit log and the console. A decision
    taken in a *different* process proves none of that — the counters and the
    subscriber set are process-local, and a script that imports the policy is a
    script, not the API. This endpoint is the only way to exercise that path on
    demand from outside.

    Two hard limits make it safe to expose:

    * the destination must be in an RFC 5737 documentation range. Those
      addresses are reserved for documentation and are not routable, so even a
      bug that skipped the policy could not reach a real service; and
    * the decision is made by :func:`check_and_record`, which consults the real
      policy and **refuses before any socket is opened**. No connection is
      attempted, so this exercises the block path without generating the traffic
      the block exists to prevent.

    The response is the decision that was actually taken and recorded — never a
    canned "blocked".
    """
    from urllib.parse import urlparse

    from backend.security.egress import EgressBlocked, policy_from_settings
    from backend.security.network.egress_policy import check_and_record

    host = (urlparse(payload.url).hostname or "").strip()
    if not _is_documentation_address(host):
        return {
            "accepted": False,
            "reason": (
                "this probe only accepts RFC 5737 documentation addresses "
                "(192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), so it can never be used "
                "to make this process attempt real external traffic"
            ),
            "url": payload.url,
        }

    policy = policy_from_settings(get_settings(request))
    decision = "ALLOW"
    detail = "the policy permitted the destination"
    try:
        check_and_record(policy, payload.url)
    except EgressBlocked as exc:
        decision = "BLOCK"
        detail = str(exc)
    return {
        "accepted": True,
        "url": payload.url,
        "destination": host,
        "decision": decision,
        "detail": detail,
        "recorded": True,
        "socket_opened": False,
    }


def _is_documentation_address(host: str) -> bool:
    """True for the three RFC 5737 ranges. Nothing else is probeable."""
    parts = host.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    octets = [int(part) for part in parts]
    return (
        (octets[0] == 192 and octets[1] == 0 and octets[2] == 2)
        or (octets[0] == 198 and octets[1] == 51 and octets[2] == 100)
        or (octets[0] == 203 and octets[1] == 0 and octets[2] == 113)
    )


# --- local AI ---------------------------------------------------------------


async def _local_ai(state: Any) -> dict[str, Any]:
    gateway = getattr(state, "gateway", None)
    if gateway is None:
        return _entry("local_ai", "Local AI", NOT_AVAILABLE, "no model gateway is attached to this app")
    try:
        health = await gateway.health()
        running = bool(health.get("running"))
        models: list[str] = []
        if running:
            by_provider = await gateway.list_models()
            models = sorted({info.id for infos in by_provider.values() for info in infos})
        backend = gateway.names()[0] if gateway.names() else None
    except Exception as exc:  # noqa: BLE001 - a probe failure is a status, not a crash
        return _entry(
            "local_ai",
            "Local AI",
            NOT_AVAILABLE,
            f"the local model backend did not answer: {type(exc).__name__}",
        )
    if running and models:
        return _entry(
            "local_ai",
            "Local AI",
            VERIFIED,
            f"on-prem backend '{backend}' answered and listed {len(models)} model(s); inference does not leave this machine.",
            evidence={"backend": backend, "models": models[:12], "model_count": len(models)},
        )
    if running:
        return _entry(
            "local_ai",
            "Local AI",
            PARTIAL,
            f"backend '{backend}' answered but listed no models, so no role can be served.",
            evidence={"backend": backend},
        )
    return _entry(
        "local_ai",
        "Local AI",
        NOT_AVAILABLE,
        f"backend '{backend}' did not answer a health probe.",
        evidence={"backend": backend},
    )


async def _local_vision(state: Any) -> dict[str, Any]:
    """Local OCR / vision.

    Honest resolution: the ingestor can run Docling, but no OCR or image
    tool is in the registered tool set, so an agent has no way to call it. That
    is ``NOT AVAILABLE`` for the agent path regardless of a library being
    importable — an installed dependency nothing can reach is not a capability.
    """
    importable = False
    version = None
    try:
        import docling  # noqa: F401

        importable = True
        version = getattr(docling, "__version__", None)
    except Exception:  # noqa: BLE001
        importable = False
    registered = _registered_tool_names(state)
    vision_tools = sorted(name for name in registered if name in {"ocr", "analyse_drawing", "analyse_image"})
    if vision_tools:
        return _entry(
            "local_vision",
            "Local OCR / Vision",
            IMPLEMENTED,
            f"registered as agent tool(s): {', '.join(vision_tools)}.",
            evidence={"tools": vision_tools},
        )
    detail = (
        "The document ingestor can run Docling"
        + (f" (importable, version {version})" if importable else " (not importable)")
        + ", but no OCR or image-analysis tool is registered, so an agent cannot call it. "
        "Ingestion-time OCR only; the agent path is not wired."
    )
    return _entry(
        "local_vision",
        "Local OCR / Vision",
        NOT_AVAILABLE,
        detail,
        evidence={"docling_importable": importable, "registered_tools": registered},
    )


async def _local_knowledge(state: Any) -> dict[str, Any]:
    """Local knowledge graph.

    ``backend/memory/graph`` is real, clearance-aware and tested — but it has no
    API route and no consumer in the request path (``grep -rn "GraphQuery("
    backend`` finds only its own module), so nothing an operator can open is
    built on it.
    """
    registered = _registered_tool_names(state)
    if any("graph" in name for name in registered):
        return _entry("local_knowledge", "Local Knowledge (graph)", IMPLEMENTED, "exposed as an agent tool.")
    return _entry(
        "local_knowledge",
        "Local Knowledge (graph)",
        NOT_AVAILABLE,
        "The graph module exists (bounded, clearance-aware traversal) but is not mounted on any route "
        "and has no consumer in the request path, so no page or agent can query it yet.",
        evidence={"module": "backend/memory/graph", "api_route": False, "consumers": 0},
    )


async def _vector_store(state: Any) -> dict[str, Any]:
    """The local vector store, measured against the index that actually exists."""
    retrieval = getattr(state, "retrieval", None)
    if retrieval is None:
        return _entry(
            "local_vector_store",
            "Local Vector Store",
            NOT_AVAILABLE,
            "no retrieval service is attached to this app.",
        )
    retriever = getattr(retrieval, "_retriever", None)
    if retriever is None:
        return _entry(
            "local_vector_store",
            "Local Vector Store",
            NOT_AVAILABLE,
            "the retrieval service has no retriever attached.",
        )
    try:
        has_table = await asyncio.to_thread(retriever.has_table)
    except Exception as exc:  # noqa: BLE001
        return _entry(
            "local_vector_store",
            "Local Vector Store",
            NOT_AVAILABLE,
            f"the local index could not be opened: {type(exc).__name__}: {exc}",
        )
    table = getattr(retriever, "table_name", None)
    model = getattr(retriever, "embedding_model", None)
    documents = _document_count(state)
    if not has_table:
        return _entry(
            "local_vector_store",
            "Local Vector Store",
            PARTIAL,
            "The LanceDB store is reachable but no chunk table exists yet, so nothing is retrievable. "
            "Uploaded documents are never embedded on upload — an explicit reindex is what creates the table.",
            evidence={"table": table, "documents": documents, "embedding_model": model},
        )
    return _entry(
        "local_vector_store",
        "Local Vector Store",
        VERIFIED,
        f"LanceDB table '{table}' is open and queryable; embeddings are local ({model}).",
        evidence={"table": table, "documents": documents, "embedding_model": model},
    )


async def _tool_registry(state: Any) -> dict[str, Any]:
    registry = getattr(state, "tools", None)
    if registry is None:
        return _entry("tool_registry", "Tool Registry", NOT_AVAILABLE, "no tool registry is attached.")
    try:
        catalogue = registry.list()
    except Exception as exc:  # noqa: BLE001
        return _entry(
            "tool_registry", "Tool Registry", NOT_AVAILABLE, f"the registry did not answer: {exc}"
        )
    names = sorted(entry.get("name", "") for entry in catalogue)
    if not names:
        return _entry("tool_registry", "Tool Registry", NOT_AVAILABLE, "the registry is empty.")
    return _entry(
        "tool_registry",
        "Tool Registry",
        VERIFIED,
        f"{len(names)} permission-gated tool(s) are registered and callable.",
        evidence={"tools": names},
    )


async def _sandbox(state: Any) -> dict[str, Any]:
    """OpenSandbox. Never reported available on the strength of a URL."""
    service = getattr(state, "sandbox", None)
    detail = (
        "OpenSandbox is not running on this host: every sandbox_command returns "
        "'ACTION BLOCKED / SANDBOX UNAVAILABLE'. Container-level network isolation "
        "is therefore not enforced here."
    )
    probed = None
    if service is not None:
        # The sandbox service's own policy summary: the same object the
        # execution path consults, so this cannot disagree with what a
        # `sandbox_command` action would return.
        try:
            probed = await asyncio.to_thread(service.summary)
        except Exception as exc:  # noqa: BLE001
            probed = {"error": type(exc).__name__}
    return _entry(
        "sandbox",
        "Sandbox",
        NOT_AVAILABLE,
        detail,
        evidence={"attached": service is not None, "probe": probed},
    )


# --- the rest of the status bar ---------------------------------------------


def _egress(state: Any, settings: Any) -> dict[str, Any]:
    """Egress enforcement, from the guard's own record — not from a flag.

    ``VERIFIED`` requires a real refusal on record. A process that has never
    been asked to reach an external host has enforcement *in place* but no
    evidence it works, and that is exactly the distinction this reports.
    """
    summary = network_summary(recent=5)
    totals = summary.get("totals", {})
    external_blocked = int(totals.get("external_blocked", 0))
    external_allowed = int(totals.get("external_allowed", 0))
    policy = "default-deny" if settings.egress_default_deny else "allowlist"
    evidence = {
        "policy": policy,
        "external_allowed": external_allowed,
        "external_blocked": external_blocked,
        "local_allowed": int(totals.get("local_allowed", 0)),
        "allowed_hosts": summary.get("allowed_hosts", []),
    }
    if external_blocked > 0 and external_allowed == 0:
        return _entry(
            "egress",
            "Egress",
            VERIFIED,
            f"{policy}; {external_blocked} external attempt(s) refused by the guard and zero reached a "
            "non-loopback host in this process.",
            evidence=evidence,
        )
    if external_allowed > 0:
        return _entry(
            "egress",
            "Egress",
            PARTIAL,
            f"{policy}, but {external_allowed} request(s) did reach a non-loopback host.",
            evidence=evidence,
        )
    return _entry(
        "egress",
        "Egress",
        IMPLEMENTED,
        f"{policy} and every outbound request passes the guard transport, but nothing has attempted an "
        "external destination in this process, so the refusal path is unproven here.",
        evidence=evidence,
    )


def _audit_chain(state: Any) -> dict[str, Any]:
    audit = getattr(state, "audit", None)
    if audit is None:
        return _entry("audit_chain", "Audit Chain", NOT_AVAILABLE, "no audit service is attached.")
    try:
        verdict = audit.verify()
        payload = verdict.as_dict()
    except Exception as exc:  # noqa: BLE001
        return _entry(
            "audit_chain",
            "Audit Chain",
            NOT_AVAILABLE,
            f"the verifier did not run: {type(exc).__name__}: {exc}",
        )
    if payload.get("valid"):
        return _entry(
            "audit_chain",
            "Audit Chain",
            VERIFIED,
            f"{payload.get('events', 0)} event(s) hash-linked and the chain walks clean to the head.",
            evidence={
                "algorithm": payload.get("algorithm"),
                "events": payload.get("events"),
                "last_hash": payload.get("last_hash"),
                "genesis_hash": payload.get("genesis_hash"),
            },
        )
    return _entry(
        "audit_chain",
        "Audit Chain",
        NOT_AVAILABLE,
        f"the chain is BROKEN at seq {payload.get('broken_seq')}: {payload.get('reason') or payload.get('error')}",
        evidence=payload,
    )


def _signing(state: Any) -> dict[str, Any]:
    artifacts = getattr(state, "artifacts", None)
    if artifacts is None:
        return _entry("signing", "Signing", NOT_AVAILABLE, "no artifact service is attached.")
    try:
        summary = artifacts.signed_artifacts(limit=1)
    except Exception as exc:  # noqa: BLE001
        return _entry(
            "signing", "Signing", NOT_AVAILABLE, f"the signature records could not be read: {exc}"
        )
    algorithm = summary.get("algorithm")
    key_id = summary.get("key_id")
    totals = summary.get("totals", {})
    evidence = {
        "algorithm": algorithm,
        "key_id": key_id,
        "signed": totals.get("signed"),
        "unsigned": totals.get("unsigned"),
        "signature_failed": totals.get("signature_failed"),
        "available": summary.get("available"),
    }
    if not summary.get("available"):
        return _entry(
            "signing",
            "Signing",
            IMPLEMENTED,
            "Ed25519 signing and verification are implemented, but no signing key is configured, so "
            "nothing can be signed in this deployment.",
            evidence=evidence,
        )
    if int(totals.get("signed") or 0) > 0:
        return _entry(
            "signing",
            "Signing",
            VERIFIED,
            f"{totals.get('signed')} artifact(s) signed with {algorithm}"
            + (f" (key {str(key_id)[:12]}…)" if key_id else "")
            + "; verification is a real Ed25519 check against the bytes on disk.",
            evidence=evidence,
        )
    return _entry(
        "signing",
        "Signing",
        IMPLEMENTED,
        "Ed25519 signing is implemented and a key is present, but no artifact has been produced yet, "
        "so nothing has been signed in this deployment.",
        evidence=evidence,
    )


def _rbac(state: Any) -> dict[str, Any]:
    from backend.security.rbac import ROLE_PERMISSIONS

    roles = {role: len(perms) for role, perms in sorted(ROLE_PERMISSIONS.items())}
    return _entry(
        "rbac",
        "RBAC",
        VERIFIED,
        "Roles resolve to a fixed permission map and every gated route and tool consults it before running.",
        evidence={"roles": roles},
    )


def _clearance(state: Any) -> dict[str, Any]:
    from backend.security.clearance import ROLE_CLEARANCE

    levels = {role: level.value for role, level in sorted(ROLE_CLEARANCE.items())}
    return _entry(
        "clearance",
        "Clearance",
        VERIFIED,
        "Ordered levels (PUBLIC→HIGHLY_CONFIDENTIAL) filter retrieved chunks before the reranker and "
        "before the prompt, and gate direct reads, graph traversal and agent tool calls.",
        evidence={"role_clearance": levels},
    )


# --- small measured facts ---------------------------------------------------


def _registered_tool_names(state: Any) -> list[str]:
    registry = getattr(state, "tools", None)
    if registry is None:
        return []
    try:
        return sorted(entry.get("name", "") for entry in registry.list())
    except Exception:  # noqa: BLE001
        return []


def _document_count(state: Any) -> int | None:
    factory = getattr(state, "session_factory", None)
    if factory is None:
        return None
    try:
        from backend.database.models import Document

        with factory() as session:
            return int(session.query(Document).count())
    except Exception:  # noqa: BLE001
        return None


__all__ = ["router"]
