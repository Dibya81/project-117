"""Routing policy.

Turns a :class:`Classification` into a concrete routing *decision*: which role
to use, with what generation limits, and whether a substitution happened.

Two rules carry the weight here:

1. **A model is never silently swapped.** The router already refuses to
   substitute one model for another. This policy may substitute a *role*
   (``domain`` → ``reasoning``) but only within the same modality, only when
   the preferred role is unconfigured, and it always records that it did so on
   the decision. Cross-modality substitution is refused outright — handing an
   image task to a text model would produce confident nonsense.

2. **Refusals are typed.** :class:`RoutingRefused` means "this task cannot be
   served by this deployment", which the caller should surface, not retry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from backend.models.router.task_classifier import (
    CODING,
    DOMAIN,
    EMBEDDING,
    KNOWN_ROLES,
    REASONING,
    RERANKER,
    VISION,
    Classification,
)


class RoutingRefused(Exception):
    """The task cannot be routed under this policy/deployment."""

    def __init__(self, message: str, *, role: str, remedy: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.role = role
        self.remedy = remedy


@dataclass(frozen=True)
class RoleLimits:
    """Generation limits per role.

    Retrieval roles carry ``max_tokens=0``: they do not generate text, and a
    non-zero budget would imply otherwise.
    """

    max_tokens: int
    temperature: float


DEFAULT_LIMITS: dict[str, RoleLimits] = {
    REASONING: RoleLimits(max_tokens=2048, temperature=0.2),
    # Low temperature for code and for anything that will be read as fact.
    CODING: RoleLimits(max_tokens=2048, temperature=0.1),
    DOMAIN: RoleLimits(max_tokens=2048, temperature=0.2),
    VISION: RoleLimits(max_tokens=1200, temperature=0.1),
    EMBEDDING: RoleLimits(max_tokens=0, temperature=0.0),
    RERANKER: RoleLimits(max_tokens=0, temperature=0.0),
}

# Only same-modality, strictly-more-general substitutions. Absence from this
# table means "no substitute exists", which is the safe default.
SUBSTITUTIONS: dict[str, tuple[str, ...]] = {
    DOMAIN: (REASONING,),
    CODING: (REASONING,),
    REASONING: (),
    VISION: (),
    EMBEDDING: (),
    RERANKER: (),
}


@dataclass(frozen=True)
class RoutingDecision:
    role: str
    max_tokens: int
    temperature: float
    classification: Classification
    substituted_from: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def generates_text(self) -> bool:
        return self.max_tokens > 0

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "substituted_from": self.substituted_from,
            "notes": list(self.notes),
            "classification": self.classification.as_dict(),
        }


class RoutingPolicy:
    def __init__(
        self,
        *,
        allowed_roles: Iterable[str] | None = None,
        limits: Mapping[str, RoleLimits] | None = None,
        allow_role_substitution: bool = True,
        max_tokens_ceiling: int | None = None,
    ) -> None:
        allowed = tuple(allowed_roles) if allowed_roles is not None else KNOWN_ROLES
        unknown = [role for role in allowed if role not in KNOWN_ROLES]
        if unknown:
            raise ValueError(f"unknown role(s) in allowed_roles: {', '.join(unknown)}")
        self._allowed = frozenset(allowed)
        self._limits = dict(DEFAULT_LIMITS)
        if limits:
            self._limits.update(limits)
        self._allow_substitution = bool(allow_role_substitution)
        self._ceiling = max_tokens_ceiling

    def allowed_roles(self) -> tuple[str, ...]:
        return tuple(role for role in KNOWN_ROLES if role in self._allowed)

    def limits_for(self, role: str) -> RoleLimits:
        if role not in self._limits:
            raise ValueError(f"no limits declared for role '{role}'")
        limits = self._limits[role]
        if self._ceiling is not None and limits.max_tokens > self._ceiling:
            return RoleLimits(max_tokens=self._ceiling, temperature=limits.temperature)
        return limits

    def decide(
        self,
        classification: Classification,
        *,
        configured_roles: Iterable[str] = (),
    ) -> RoutingDecision:
        """Resolve a classification to a usable role.

        ``configured_roles`` is what the deployment actually has models for.
        Passing an empty collection disables the availability check, which is
        useful for planning-time decisions made before any provider is
        contacted.
        """
        preferred = classification.role
        if preferred not in KNOWN_ROLES:
            raise ValueError(f"classification names unknown role '{preferred}'")

        if preferred not in self._allowed:
            raise RoutingRefused(
                f"role '{preferred}' is disabled by policy for this deployment",
                role=preferred,
                remedy=f"enabled roles are: {', '.join(self.allowed_roles())}",
            )

        configured = frozenset(configured_roles)
        notes: list[str] = []

        # No availability information supplied: decide on policy alone.
        if not configured:
            limits = self.limits_for(preferred)
            return RoutingDecision(
                role=preferred,
                max_tokens=limits.max_tokens,
                temperature=limits.temperature,
                classification=classification,
                notes=("availability was not checked at decision time",),
            )

        if preferred in configured:
            limits = self.limits_for(preferred)
            return RoutingDecision(
                role=preferred,
                max_tokens=limits.max_tokens,
                temperature=limits.temperature,
                classification=classification,
            )

        if not self._allow_substitution:
            raise RoutingRefused(
                f"role '{preferred}' has no configured model and substitution is disabled",
                role=preferred,
                remedy="configure the role or enable allow_role_substitution",
            )

        for candidate in SUBSTITUTIONS.get(preferred, ()):
            if candidate in configured and candidate in self._allowed:
                limits = self.limits_for(candidate)
                notes.append(
                    f"'{preferred}' is unconfigured; used the more general "
                    f"'{candidate}' role instead (same modality)"
                )
                return RoutingDecision(
                    role=candidate,
                    max_tokens=limits.max_tokens,
                    temperature=limits.temperature,
                    classification=classification,
                    substituted_from=preferred,
                    notes=tuple(notes),
                )

        raise RoutingRefused(
            f"role '{preferred}' has no configured model and no same-modality "
            f"substitute is available",
            role=preferred,
            remedy=(
                "configure a model for this role; cross-modality substitution is "
                "refused on purpose because it would produce confident nonsense"
            ),
        )


__all__ = [
    "DEFAULT_LIMITS",
    "SUBSTITUTIONS",
    "RoleLimits",
    "RoutingDecision",
    "RoutingPolicy",
    "RoutingRefused",
]
