"""Model registry.

One place to answer three questions: *what roles exist*, *what model is
configured for each*, and *is that model actually served right now*.

Role **definitions** deliberately live beside each role package
(``backend.models.reasoning``, ``.vision``, ...) rather than in one central
table here. Adding a role should mean adding a package, not editing a table
that every role already depends on. This module only *assembles* those
declarations and joins them against configuration and provider availability.

The assembly import is deferred into :func:`load_descriptors` on purpose: the
role packages import :class:`RoleDescriptor` from this module, so importing
them at module scope here would be a circular import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.models import ModelRoles
    from backend.models.gateway.model_gateway import ModelGateway

# Canonical role order. Kept in one place so /api/models, health checks and
# the router all report roles in the same sequence.
ROLE_ORDER: tuple[str, ...] = (
    "reasoning",
    "vision",
    "embedding",
    "reranker",
    "coding",
    "domain",
)


class UnknownRole(KeyError):
    """Asked about a role that does not exist.

    A distinct type because "you asked for a role I don't have" is a caller
    bug, whereas "the role exists but has no model" is an operator
    configuration issue reported through ``ModelUnavailableError``.
    """


@dataclass(frozen=True)
class RoleDescriptor:
    """What a role is for, and what it needs before it can be used.

    ``suggested_models`` is documentation for whoever writes ``.env`` --
    never a default the code silently falls back to. A role with no
    configured model stays unavailable.
    """

    role: str
    purpose: str
    setting: str
    modalities: tuple[str, ...] = ("text",)
    capabilities: tuple[str, ...] = ()
    suggested_models: tuple[str, ...] = ()
    required_for_demo: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "purpose": self.purpose,
            "setting": self.setting,
            "modalities": list(self.modalities),
            "capabilities": list(self.capabilities),
            "suggested_models": list(self.suggested_models),
            "required_for_demo": self.required_for_demo,
            "notes": self.notes,
        }


@dataclass
class RoleStatus:
    """Configuration + availability for one role at a point in time."""

    role: str
    configured: bool
    model: str | None
    served: bool | None  # None => availability could not be determined
    setting: str
    required_for_demo: bool
    reason: str = ""
    descriptor: RoleDescriptor | None = field(default=None, repr=False)

    @property
    def usable(self) -> bool:
        return bool(self.configured and self.served)

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "configured": self.configured,
            "model": self.model,
            "served": self.served,
            "usable": self.usable,
            "setting": self.setting,
            "required_for_demo": self.required_for_demo,
            "reason": self.reason,
        }


def load_descriptors() -> dict[str, RoleDescriptor]:
    """Collect descriptors from the role packages.

    Deferred import (see module docstring). A role package that fails to
    import is a hard error rather than a skipped role: silently dropping a
    role would make the registry under-report what the system needs.
    """
    from backend.models import coding, domain, embeddings, reasoning, vision

    collected: dict[str, RoleDescriptor] = {}
    for module in (reasoning, vision, embeddings, coding, domain):
        for descriptor in getattr(module, "DESCRIPTORS", ()):
            if descriptor.role in collected:
                raise ValueError(
                    f"role '{descriptor.role}' is declared twice "
                    f"(second declaration in {module.__name__})"
                )
            collected[descriptor.role] = descriptor
    return collected


class ModelRegistry:
    """Joins role declarations, configuration and live availability.

    ``descriptors`` is injectable so this class can be exercised without
    importing the whole ``backend.models`` package (and therefore settings).
    """

    def __init__(
        self,
        roles: "ModelRoles",
        descriptors: Mapping[str, RoleDescriptor] | None = None,
    ) -> None:
        self._roles = roles
        self._descriptors: dict[str, RoleDescriptor] = dict(
            descriptors if descriptors is not None else load_descriptors()
        )
        missing = [r for r in ROLE_ORDER if r not in self._descriptors]
        if missing:
            raise ValueError("no descriptor declared for role(s): " + ", ".join(missing))

    # --- declarations ----------------------------------------------------

    def roles(self) -> tuple[str, ...]:
        return ROLE_ORDER

    def descriptor(self, role: str) -> RoleDescriptor:
        try:
            return self._descriptors[role]
        except KeyError as exc:
            raise UnknownRole(
                f"unknown model role '{role}' (known: {', '.join(ROLE_ORDER)})"
            ) from exc

    def descriptors(self) -> list[RoleDescriptor]:
        return [self._descriptors[role] for role in ROLE_ORDER]

    def configured_model(self, role: str) -> str | None:
        self.descriptor(role)  # validates the role name
        return self._roles.get(role)

    def required_roles(self) -> tuple[str, ...]:
        return tuple(role for role in ROLE_ORDER if self._descriptors[role].required_for_demo)

    def configuration_problems(self) -> list[str]:
        """Operator-facing configuration gaps.

        Only *required* roles are problems. An unconfigured optional role is a
        deliberate deployment choice (no vision model on a text-only box), and
        reporting it as a problem would train operators to ignore this list.
        """
        problems: list[str] = []
        for role in self.required_roles():
            if not self._roles.get(role):
                descriptor = self._descriptors[role]
                problems.append(
                    f"role '{role}' is required but unset - set "
                    f"{descriptor.setting} (see .env.example)"
                )
        return problems

    def check_router_agreement(self, router_roles: Sequence[str]) -> list[str]:
        """Guard against the registry and router drifting apart.

        Two independent tuples of role names is exactly the kind of
        duplication that rots, so it is checked rather than trusted.
        """
        problems: list[str] = []
        for role in router_roles:
            if role not in self._descriptors:
                problems.append(f"router resolves '{role}' but the registry has no descriptor")
        for role in ROLE_ORDER:
            if role not in router_roles:
                problems.append(f"registry declares '{role}' but the router cannot resolve it")
        return problems

    # --- live status -----------------------------------------------------

    def status(self, *, available_models: Iterable[str] | None = None) -> list[RoleStatus]:
        """Status for every role.

        ``available_models=None`` means availability is *unknown* (the backend
        was not reachable). That is reported as ``served=None`` rather than
        ``False``, because "we could not tell" and "the model is missing" call
        for different operator actions.
        """
        served_set = None if available_models is None else set(available_models)
        result: list[RoleStatus] = []
        for role in ROLE_ORDER:
            descriptor = self._descriptors[role]
            model = self._roles.get(role)
            if not model:
                result.append(
                    RoleStatus(
                        role=role,
                        configured=False,
                        model=None,
                        served=False,
                        setting=descriptor.setting,
                        required_for_demo=descriptor.required_for_demo,
                        reason=f"{descriptor.setting} is not set",
                        descriptor=descriptor,
                    )
                )
                continue
            if served_set is None:
                reason = "provider unreachable, availability unknown"
                served: bool | None = None
            elif model in served_set:
                reason = ""
                served = True
            else:
                reason = f"'{model}' is not served by the local backend"
                served = False
            result.append(
                RoleStatus(
                    role=role,
                    configured=True,
                    model=model,
                    served=served,
                    setting=descriptor.setting,
                    required_for_demo=descriptor.required_for_demo,
                    reason=reason,
                    descriptor=descriptor,
                )
            )
        return result

    async def snapshot(self, gateway: "ModelGateway") -> dict[str, Any]:
        """Registry status joined with what the gateway can currently see."""
        by_provider = await gateway.list_models()
        served: set[str] = set()
        reachable = False
        for infos in by_provider.values():
            if infos:
                reachable = True
            served.update(info.id for info in infos)
        statuses = self.status(available_models=served if reachable else None)
        return {
            "roles": [status.as_dict() for status in statuses],
            "declarations": [d.as_dict() for d in self.descriptors()],
            "served_models": sorted(served),
            "providers": sorted(by_provider),
            "problems": self.configuration_problems(),
            "ready": all(s.usable for s in statuses if s.required_for_demo),
        }


__all__ = [
    "ROLE_ORDER",
    "ModelRegistry",
    "RoleDescriptor",
    "RoleStatus",
    "UnknownRole",
    "load_descriptors",
]
