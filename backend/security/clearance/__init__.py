"""Clearance model — permission-aware retrieval (Phase 4 extension).

RBAC answers *"who may perform this action"*. It does not answer *"which
documents may this user's model context contain"*: every role with
``SEARCH_QUERY`` could retrieve every chunk in the index, because retrieval had
no notion of a document's sensitivity. The two questions are different and this
module adds the second one without redesigning the first —
:mod:`backend.security.rbac` is extended, not replaced.

The levels are ordered, so "confidential" implies access to everything below it:

    PUBLIC < INTERNAL < RESTRICTED < CONFIDENTIAL < HIGHLY_CONFIDENTIAL

Flow enforced end to end::

    User → Role → Clearance → Retriever → authorized content ONLY → model context

The enforcement points, all of them *before* the content reaches a model:

* :meth:`backend.rag.service.RetrievalService.search` filters chunks before the
  reranker and before any :class:`~backend.rag.service.Evidence` is built, so an
  unauthorized chunk is not in the list a reranker scores or a prompt cites.
* :func:`backend.security.clearance.access.require_document_clearance` gates a
  direct document read.
* :func:`backend.security.clearance.access.visible_node` gates graph traversal,
  so a restricted document cannot be reached by walking to it.
* The tool registry carries the caller's roles into every tool, so an agent's
  tool call is filtered by exactly the same rules as an interactive search.

Three decisions worth stating explicitly:

**Unlabelled means the default, not public.** A document with no clearance
metadata is :data:`DEFAULT_CLEARANCE` (INTERNAL). Treating "no label" as
public would make every pre-existing document world-readable the moment this
model shipped, which is the exact failure mode a clearance system exists to
prevent. Assets that genuinely are public are labelled public.

**The level is not the role.** ``ROLE_CLEARANCE`` maps the existing roles to a
default level so a deployment gets sane behaviour without a second identity
system, but a principal may carry an explicit clearance (see
``Principal.extra["clearance"]``) — a contractor with an operator role and an
INTERNAL badge is a real configuration.

**Deny is a refusal, not an empty result.** ``ClearanceDenied`` is raised for a
direct lookup; a search filters silently (a search is a query, not a claim about
one record) and reports how many results were withheld, so an operator can tell
"nothing matched" from "something matched that you may not see".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from backend.security.rbac import Principal


class Clearance(str, Enum):
    """Sensitivity of a document, chunk, graph entity or artifact.

    Ordered by ``rank``; comparison operators are provided so a check reads as
    ``principal.clearance >= document.clearance`` rather than as arithmetic on
    an integer someone has to look up.
    """

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"
    HIGHLY_CONFIDENTIAL = "HIGHLY_CONFIDENTIAL"

    @property
    def rank(self) -> int:
        return _RANK[self]

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, Clearance):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, Clearance):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, Clearance):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, Clearance):
            return NotImplemented
        return self.rank >= other.rank


_RANK: dict[Clearance, int] = {level: index for index, level in enumerate(Clearance)}

#: What an unlabelled asset is worth. INTERNAL, not PUBLIC: see the module
#: docstring. Changing this changes the blast radius of every existing document.
DEFAULT_CLEARANCE = Clearance.INTERNAL

#: What an unlabelled *graph entity* is worth.
#:
#: Deliberately different from :data:`DEFAULT_CLEARANCE`. A knowledge-graph
#: node is usually a structural fact — equipment tags, sites, signals, work
#: order numbers — and none of those are secret; defaulting them to INTERNAL
#: would hide an entire plant's topology from a viewer the moment this model
#: shipped, which is a broken console rather than a conservative policy.
#: Records whose *content* is sensitive (documents, procedures) are labelled at
#: their source and are held to that label whether they are read directly or
#: reached by traversal.
DEFAULT_ENTITY_CLEARANCE = Clearance.PUBLIC

#: The clearance a role confers when the principal carries no explicit badge.
#: One step per role, mirroring how the roles already nest:
#: viewer ⊂ analyst ⊂ operator ⊂ admin.
ROLE_CLEARANCE: dict[str, Clearance] = {
    "viewer": Clearance.PUBLIC,
    "analyst": Clearance.INTERNAL,
    "field": Clearance.RESTRICTED,
    "operator": Clearance.RESTRICTED,
    "admin": Clearance.HIGHLY_CONFIDENTIAL,
}

#: Aliases accepted from callers and from stored metadata. Keys are normalised
#: to upper case with spaces/hyphens folded to underscores before lookup, so
#: "highly confidential", "Highly-Confidential" and "HIGHLY_CONFIDENTIAL" are
#: one level rather than three.
_ALIASES: dict[str, Clearance] = {
    "PUBLIC": Clearance.PUBLIC,
    "UNCLASSIFIED": Clearance.PUBLIC,
    "INTERNAL": Clearance.INTERNAL,
    "RESTRICTED": Clearance.RESTRICTED,
    "CONFIDENTIAL": Clearance.CONFIDENTIAL,
    "HIGHLY_CONFIDENTIAL": Clearance.HIGHLY_CONFIDENTIAL,
    "HIGHLYCONFIDENTIAL": Clearance.HIGHLY_CONFIDENTIAL,
    "TOP_SECRET": Clearance.HIGHLY_CONFIDENTIAL,
    "SECRET": Clearance.CONFIDENTIAL,
}


class ClearanceError(ValueError):
    """An unparseable clearance value. Never silently coerced."""

    reason = "clearance_invalid"


class ClearanceDenied(PermissionError):
    """The caller's clearance does not reach this asset.

    Deliberately a :class:`PermissionError` so existing call sites that treat a
    permission failure as a refusal keep doing so. ``reason`` matches the
    tool-registry vocabulary ("denied") so an audit row records a refusal.
    """

    reason = "denied"

    def __init__(
        self,
        message: str,
        *,
        required: Clearance | None = None,
        held: Clearance | None = None,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.required = required.value if required else None
        self.held = held.value if held else None
        self.resource_id = resource_id


def parse_clearance(value: Any, *, default: Clearance | None = None) -> Clearance:
    """Coerce ``value`` to a :class:`Clearance`.

    Accepts a Clearance, its name in any case/separator style, or ``None``.
    ``None`` (and the empty string) yields ``default`` when one was supplied,
    otherwise :data:`DEFAULT_CLEARANCE`. Anything else raises rather than
    guessing: a typo in a metadata field must not silently widen access, and it
    must not silently narrow it either (a document that became unreadable
    because someone wrote "Restriced" would be found by a human, not by a
    policy that guessed).
    """
    if isinstance(value, Clearance):
        return value
    if value is None or (isinstance(value, str) and not value.strip()):
        return default or DEFAULT_CLEARANCE
    key = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    found = _ALIASES.get(key)
    if found is None:
        raise ClearanceError(
            f"unknown clearance {value!r}; expected one of: "
            + ", ".join(level.value for level in Clearance)
        )
    return found


def clearance_for_roles(roles: Iterable[str] | None) -> Clearance:
    """The highest clearance any of ``roles`` confers.

    Union, matching :func:`backend.security.rbac.permissions_for`: holding two
    roles grants the union of what they grant, never less.
    """
    levels = [
        ROLE_CLEARANCE[str(role).strip().lower()]
        for role in (roles or ())
        if str(role).strip().lower() in ROLE_CLEARANCE
    ]
    return max(levels, key=lambda level: level.rank) if levels else Clearance.PUBLIC


def principal_clearance(principal: Principal | None) -> Clearance:
    """The clearance ``principal`` actually holds.

    An explicit badge in ``principal.extra["clearance"]`` wins over the role
    default, so a named user can be given more or less than their role implies
    without inventing a second role vocabulary. An explicit badge may *lower* a
    principal's clearance (a contractor with an operator role and an INTERNAL
    badge) as well as raise it; that is the point of an explicit grant.
    """
    if principal is None:
        return DEFAULT_CLEARANCE
    explicit = (principal.extra or {}).get("clearance")
    if explicit is not None:
        return parse_clearance(explicit)
    return clearance_for_roles(principal.roles)


@dataclass(frozen=True)
class ClearanceVerdict:
    """The outcome of one access check, with everything needed to explain it."""

    allowed: bool
    required: Clearance
    held: Clearance
    resource_id: str | None = None

    @property
    def reason(self) -> str:
        if self.allowed:
            return f"clearance {self.held.value} covers {self.required.value}"
        return (
            f"clearance {self.held.value} is below the {self.required.value} "
            "required by this resource"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "required": self.required.value,
            "held": self.held.value,
            "resource_id": self.resource_id,
            "reason": self.reason,
        }


def check_clearance(
    held: Clearance | Principal | None,
    required: Any,
    *,
    resource_id: str | None = None,
) -> ClearanceVerdict:
    """Compare a caller's clearance against an asset's. Does not raise."""
    held_level = principal_clearance(held) if isinstance(held, Principal) or held is None else held
    required_level = parse_clearance(required)
    return ClearanceVerdict(
        allowed=held_level >= required_level,
        required=required_level,
        held=held_level,
        resource_id=resource_id,
    )


def allowed(
    held: Clearance | Principal | None, required: Any, *, resource_id: str | None = None
) -> bool:
    return check_clearance(held, required, resource_id=resource_id).allowed


def clearance_of(metadata: Mapping[str, Any] | None, *, key: str = "clearance") -> Clearance:
    """Read the clearance out of a metadata mapping.

    Both spellings are accepted because two producers write this field:
    ingestion writes ``metadata["clearance"]`` for a document, and graph
    entities carry ``attributes["clearance"]``. The nested
    ``metadata["ingestion"]["clearance"]`` form is honoured so a document
    labelled at ingest time keeps one label rather than two.
    """
    if not metadata:
        return DEFAULT_CLEARANCE
    raw = metadata.get(key)
    if raw is None:
        nested = metadata.get("ingestion")
        if isinstance(nested, Mapping):
            raw = nested.get(key)
    if raw is None:
        # ``classification`` is the synonym used by some DMS exports.
        raw = metadata.get("classification")
    return parse_clearance(raw)


def entity_clearance(metadata: Mapping[str, Any] | None, *, key: str = "clearance") -> Clearance:
    """The clearance of a graph entity's attributes.

    Same parsing as :func:`clearance_of`, different default: an unlabelled
    entity is :data:`DEFAULT_ENTITY_CLEARANCE`. See that constant for why the
    default differs from a document's.
    """
    if not metadata:
        return DEFAULT_ENTITY_CLEARANCE
    raw = metadata.get(key)
    if raw is None:
        raw = metadata.get("classification")
    if raw is None:
        return DEFAULT_ENTITY_CLEARANCE
    return parse_clearance(raw)


__all__ = [
    "DEFAULT_CLEARANCE",
    "DEFAULT_ENTITY_CLEARANCE",
    "ROLE_CLEARANCE",
    "Clearance",
    "ClearanceDenied",
    "ClearanceError",
    "ClearanceVerdict",
    "allowed",
    "check_clearance",
    "clearance_for_roles",
    "clearance_of",
    "entity_clearance",
    "parse_clearance",
    "principal_clearance",
]
