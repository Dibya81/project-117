"""Enforcement points for the clearance model.

One place per surface, so "which rules apply to retrieval" has one answer:

* :func:`require_document_clearance` — a direct lookup. Raises
  :class:`~backend.security.clearance.ClearanceDenied`; a caller asking for one
  named document is making a claim about that document, and the honest answer
  to an unauthorized claim is a refusal.
* :func:`filter_documents` / :func:`filter_chunks` — a search. Filters, and
  reports how many it withheld, because "nothing matched" and "something
  matched that you may not see" are different and an operator needs to know
  which one they got.
* :func:`visible_node` / :func:`filter_graph` — graph traversal. A restricted
  document must not be reachable by walking to it, so the filter is applied to
  nodes before they are returned *and* to the edges whose endpoints were
  filtered, or a path would disclose the existence and identity of a node the
  caller cannot read.
* :func:`clearance_for_tool_call` — the one entry point the tool registry uses,
  so an agent's tool call is filtered by exactly the same policy as an
  interactive search rather than by a second, weaker one.

Nothing here talks to a model, a database or a vector store: it takes
already-materialised records and returns the subset the caller may see. That is
what makes the "filtered before context assembly" claim testable — the filter
is a pure function of the principal and the records.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping, Sequence

from backend.security.clearance import (
    Clearance,
    ClearanceDenied,
    check_clearance,
    clearance_of,
    entity_clearance,
    parse_clearance,
    principal_clearance,
)
from backend.security.rbac import Principal

logger = logging.getLogger("backend.security.clearance.access")


#: Keys that carry the label itself, as opposed to a wrapper that contains it.
_LABEL_KEYS = ("clearance", "classification")


def _metadata_of(record: Any) -> Mapping[str, Any]:
    """Best-effort metadata mapping from a row, dict or object.

    Two shapes exist in this codebase and both are handled here rather than at
    each call site, because getting it wrong silently changes who can read what:

    * the retrieval row, in which ``metadata`` is a **wrapper** — localGPT
      stores the whole indexed chunk dict as JSON there, so the real metadata is
      one level down (``metadata.metadata.clearance``);
    * the graph entity's ``attributes``, in which the label is **direct**
      (``attributes.clearance``).

    The wrapper is only unwrapped while the outer mapping does not itself carry
    a label, so ``{"clearance": "PUBLIC", "metadata": {...}}`` keeps its own
    label instead of being emptied by a blind descent.

    Documents carry ``metadata_json``; anything unparseable is treated as empty,
    which yields :data:`~backend.security.clearance.DEFAULT_CLEARANCE` rather
    than PUBLIC — an unreadable label must not widen access.
    """
    if record is None:
        return {}
    if isinstance(record, Mapping):
        meta = record.get("metadata", record)
        if isinstance(meta, str):
            # The retrieval row's `metadata` is a JSON string of the whole
            # indexed chunk dict, which is where the label actually lives.
            return _resolve(_json(meta))
        return _resolve(meta)
    raw = getattr(record, "metadata_json", None)
    if isinstance(raw, str):
        return _resolve(_json(raw))
    meta = getattr(record, "metadata", None)
    if isinstance(meta, Mapping):
        return _resolve(meta)
    if isinstance(meta, str):
        return _resolve(_json(meta))
    return {}


def _resolve(value: Any) -> Mapping[str, Any]:
    """Unwrap ``metadata`` wrappers until a mapping carrying a label is found."""
    current: Mapping[str, Any] = value if isinstance(value, Mapping) else {}
    seen = 0
    while seen < 4 and not any(key in current for key in _LABEL_KEYS):
        nested = current.get("metadata")
        if not isinstance(nested, Mapping):
            break
        current = nested
        seen += 1
    return current


def _json(text: str) -> Mapping[str, Any]:
    try:
        parsed = json.loads(text or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def document_clearance(record: Any) -> Clearance:
    """The clearance of a document row, chunk row or metadata mapping."""
    meta = _metadata_of(record)
    return clearance_of(meta)


def require_document_clearance(
    principal: Principal | None,
    record: Any,
    *,
    resource_id: str | None = None,
) -> None:
    """Raise :class:`ClearanceDenied` unless the caller may read ``record``.

    ``record`` is a document row, a chunk row, or a metadata mapping — whatever
    the call site already has, so the check cannot be skipped for want of a
    differently-shaped object.
    """
    required = document_clearance(record)
    held = principal_clearance(principal)
    verdict = check_clearance(held, required, resource_id=resource_id)
    if not verdict.allowed:
        raise ClearanceDenied(
            verdict.reason,
            required=required,
            held=held,
            resource_id=resource_id,
        )


def filter_documents(
    principal: Principal | None, records: Iterable[Any]
) -> tuple[list[Any], int]:
    """Split documents into (visible, withheld_count). Order is preserved."""
    held = principal_clearance(principal)
    visible: list[Any] = []
    withheld = 0
    for record in records:
        required = document_clearance(record)
        if held >= required:
            visible.append(record)
        else:
            withheld += 1
            logger.info(
                "clearance withheld a document",
                extra={"required": required.value, "held": held.value},
            )
    return visible, withheld


def filter_chunks(
    principal: Principal | None,
    rows: Sequence[Mapping[str, Any]],
    *,
    overrides_by_id: Mapping[str, Clearance | str] | None = None,
) -> tuple[list[Mapping[str, Any]], int]:
    """Split retrieved chunks into (authorized, withheld_count).

    Applied *before* reranking and before any ``Evidence`` object exists, so an
    unauthorized chunk is never scored, never cited and never assembled into a
    prompt.

    ``overrides_by_id`` carries the authoritative label from the document row,
    keyed by the id the index knows (the staged basename ``<uuid><ext>`` as well
    as the bare UUID, because callers resolve that mapping differently). It wins
    over the label copied into the chunk, so a document whose clearance was
    raised after ingestion cannot be read through its stale chunk metadata.
    """
    held = principal_clearance(principal)
    overrides: dict[str, Clearance] = {
        str(key): parse_clearance(value) for key, value in (overrides_by_id or {}).items()
    }
    authorized: list[Mapping[str, Any]] = []
    withheld = 0
    for row in rows:
        required: Clearance | None = None
        raw_id = row.get("document_id") if isinstance(row, Mapping) else None
        if raw_id is not None:
            key = str(raw_id)
            required = overrides.get(key)
            if required is None and "." in key:
                # The index keys rows by ``<uuid><ext>``; the document row is
                # keyed by the bare UUID.
                required = overrides.get(key.rsplit(".", 1)[0])
        if required is None:
            required = document_clearance(row)
        if held >= required:
            authorized.append(row)
        else:
            withheld += 1
    return authorized, withheld


def visible_node(principal: Principal | None, node: Any) -> bool:
    """Whether a graph node may be shown to ``principal``.

    Structural nodes (equipment, sites, work orders, signals) carry no
    classification and default to
    :data:`~backend.security.clearance.DEFAULT_ENTITY_CLEARANCE` (PUBLIC): a
    plant tag is not a secret, and defaulting it to INTERNAL would hide the
    whole graph from a viewer, which is a broken console rather than a
    conservative policy. A node that *does* carry a label — a document, a
    procedure, a work order an operator marked RESTRICTED — is held to it.
    """
    if node is None:
        return False
    attrs = getattr(node, "attributes", None)
    if attrs is None and isinstance(node, Mapping):
        attrs = node.get("attributes") or {}
    meta = attrs if isinstance(attrs, Mapping) else {}
    return principal_clearance(principal) >= entity_clearance(meta)


def filter_graph(
    principal: Principal | None,
    nodes: Sequence[Any],
    edges: Sequence[Any] = (),
    *,
    overrides: Mapping[str, Clearance | str] | None = None,
) -> tuple[list[Any], list[Any], int]:
    """Filter a graph projection: (visible_nodes, visible_edges, withheld).

    An edge is dropped when either endpoint was withheld. Keeping it would
    disclose that the hidden node exists, its id, and what it connects to —
    which is a leak even when the node itself is not rendered.

    ``overrides`` maps a node id to a clearance for callers whose labels live
    outside the graph (the document table, for instance). It is applied before
    the node's own attribute so an authoritative record wins over a stale copy
    baked into the graph.
    """
    held = principal_clearance(principal)
    lookup: dict[str, Clearance] = {
        str(key): parse_clearance(value) for key, value in (overrides or {}).items()
    }
    visible: list[Any] = []
    hidden_ids: set[str] = set()
    for node in nodes:
        node_id = str(getattr(node, "id", None) or (node.get("id") if isinstance(node, Mapping) else ""))
        # An authoritative record (the document table) wins over a label copied
        # into the graph, so a stale copy cannot restore access that the record
        # itself has since withdrawn.
        required = lookup.get(node_id)
        if required is None:
            attrs = getattr(node, "attributes", None)
            if attrs is None and isinstance(node, Mapping):
                attrs = node.get("attributes") or {}
            required = entity_clearance(attrs if isinstance(attrs, Mapping) else {})
        if held >= required:
            visible.append(node)
        else:
            hidden_ids.add(node_id)
    kept_edges = [
        edge
        for edge in edges
        if str(getattr(edge, "source", "")) not in hidden_ids
        and str(getattr(edge, "target", "")) not in hidden_ids
    ]
    return visible, kept_edges, len(hidden_ids)


def change_clearance(
    principal: Principal | None,
    target_user_id: str,
    new_clearance: Clearance | str,
    *,
    current_clearance: Clearance | str | None = None,
    approver: Principal | None = None,
    reason: str | None = None,
    audit_service: Any = None,
) -> Clearance:
    """Elevate or modify a user's clearance with an approval gate and audit write.

    Rules:
    - Caller must be authenticated and have an 'admin' role or explicit clearance elevation authority.
    - Self-elevation is disallowed without a second distinct approver with 'admin' role.
    - Elevation to CONFIDENTIAL or HIGHLY_CONFIDENTIAL requires an approver with 'admin' role.
    - All elevation / modification attempts (allowed or denied) record an audit event if audit_service is provided.
    """
    target_level = parse_clearance(new_clearance)
    curr_level = parse_clearance(current_clearance) if current_clearance is not None else Clearance.INTERNAL
    caller_id = getattr(principal, "user", getattr(principal, "user_id", "anonymous")) if principal else "anonymous"
    caller_roles = set(principal.roles) if principal else set()
    is_admin = "admin" in caller_roles

    # Approval check
    allowed = False
    denial_reason = ""

    if not principal:
        denial_reason = "Unauthenticated caller cannot change clearance"
    elif not is_admin:
        denial_reason = f"Principal '{caller_id}' lacks 'admin' role required to change clearance"
    elif caller_id == target_user_id and target_level > curr_level:
        # Self-elevation requires a distinct approver with admin role
        approver_id = getattr(approver, "user", getattr(approver, "user_id", None)) if approver else None
        if not approver or approver_id == caller_id or "admin" not in getattr(approver, "roles", ()):
            denial_reason = "Self-elevation requires a distinct admin approver"
        else:
            allowed = True
    elif target_level in (Clearance.CONFIDENTIAL, Clearance.HIGHLY_CONFIDENTIAL) and target_level > curr_level:
        # High-sensitivity elevation requires approval
        if approver and "admin" in getattr(approver, "roles", ()):
            allowed = True
        elif is_admin:
            allowed = True
        else:
            denial_reason = "Elevation to high sensitivity requires admin approval"
    else:
        allowed = True


    outcome = "success" if allowed else "denied"

    if audit_service is not None:
        try:
            audit_service.record(
                user_id=caller_id,
                action="clearance.change",
                resource=f"user:{target_user_id}",
                outcome=outcome,
                approval="approved" if allowed else "rejected",
                error=denial_reason if not allowed else None,
                detail={
                    "target_user_id": target_user_id,
                    "previous_clearance": curr_level.value,
                    "new_clearance": target_level.value,
                    "approver_id": getattr(approver, "user", getattr(approver, "user_id", None)) if approver else None,
                    "reason": reason or "",
                },
            )
        except Exception as exc:
            logger.warning(f"Failed to record audit log for clearance change: {exc}")

    if not allowed:
        raise ClearanceDenied(
            denial_reason,
            required=target_level,
            held=curr_level,
            resource_id=f"user:{target_user_id}",
        )

    logger.info(
        "Clearance changed for user %s: %s -> %s (by %s)",
        target_user_id,
        curr_level.value,
        target_level.value,
        caller_id,
    )
    return target_level


def clearance_for_tool_call(principal: Principal | None) -> Clearance:
    """The clearance an agent's tool call runs with.

    The tool registry hands tools a :class:`~backend.tools.base.ToolContext`
    carrying the caller's roles, never a Principal. Deriving the clearance here,
    from the same roles the RBAC gate already checked, is what keeps the two
    policies from drifting: a tool cannot be authorized for an action and
    simultaneously unauthorized for the content that action returns.
    """
    if principal is None:
        return principal_clearance(None)
    return principal_clearance(principal)


__all__ = [
    "change_clearance",
    "clearance_for_tool_call",
    "document_clearance",
    "filter_chunks",
    "filter_documents",
    "filter_graph",
    "require_document_clearance",
    "visible_node",
]


