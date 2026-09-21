"""Model-layer health checks.

Readiness is defined as *the roles this deployment needs are backed by models
the backend actually serves* — not "the HTTP port answered". A provider that
is up but serving none of the configured models is reported as degraded, not
healthy, because from the application's point of view it cannot do any work.

``list_models`` is used as the probe rather than a bare ping: it is the same
call the router relies on for availability, so a green health check and a
working request are backed by the same evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.models.providers.base import (
    ProviderEgressBlocked,
    ProviderHttpError,
    ProviderUnreachable,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.models.gateway.model_gateway import ModelGateway
    from backend.models.gateway.model_registry import ModelRegistry


@dataclass
class ProviderHealth:
    name: str
    running: bool
    latency_ms: int | None = None
    models_served: int = 0
    error: str | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "running": self.running,
            "latency_ms": self.latency_ms,
            "models_served": self.models_served,
            "error": self.error,
            "error_code": self.error_code,
        }


class HealthChecker:
    def __init__(
        self,
        gateway: "ModelGateway",
        registry: "ModelRegistry | None" = None,
    ) -> None:
        self._gateway = gateway
        self._registry = registry

    async def check_providers(self) -> tuple[list[ProviderHealth], set[str], bool]:
        """Probe every provider.

        Returns the per-provider report, the union of served model ids, and
        whether *any* provider answered. The last flag matters: if nothing
        answered, model availability is unknown rather than absent.
        """
        reports: list[ProviderHealth] = []
        served: set[str] = set()
        any_reachable = False

        for name in self._gateway.names():
            provider = self._gateway.provider(name)
            started = time.monotonic()
            try:
                infos = await provider.list_models()
            except ProviderEgressBlocked as exc:
                reports.append(
                    ProviderHealth(
                        name=name,
                        running=False,
                        error=str(exc),
                        error_code="egress_blocked",
                    )
                )
                continue
            except (ProviderUnreachable, ProviderHttpError) as exc:
                reports.append(
                    ProviderHealth(
                        name=name,
                        running=False,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        error=str(exc),
                        error_code=getattr(exc, "code", "provider_error"),
                    )
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive
                reports.append(
                    ProviderHealth(
                        name=name,
                        running=False,
                        error=f"{type(exc).__name__}: {exc}",
                        error_code="unexpected_error",
                    )
                )
                continue

            any_reachable = True
            ids = {info.id for info in infos}
            served.update(ids)
            reports.append(
                ProviderHealth(
                    name=name,
                    running=True,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    models_served=len(ids),
                )
            )

        return reports, served, any_reachable

    async def check(self) -> dict[str, Any]:
        providers, served, any_reachable = await self.check_providers()
        degraded: list[str] = []

        for report in providers:
            if not report.running:
                degraded.append(f"provider '{report.name}' is not answering: {report.error}")
            elif report.models_served == 0:
                degraded.append(f"provider '{report.name}' is up but serves no models")

        payload: dict[str, Any] = {
            "ready": False,
            "providers": [report.as_dict() for report in providers],
            "served_models": sorted(served),
        }

        if self._registry is None:
            # Without the registry we can only report transport health, and we
            # say so rather than implying role readiness was checked.
            payload["ready"] = any_reachable and bool(served)
            payload["roles"] = []
            degraded.append("no model registry was supplied; role readiness was not evaluated")
            payload["degraded"] = degraded
            return payload

        statuses = self._registry.status(available_models=served if any_reachable else None)
        for status in statuses:
            if status.required_for_demo and not status.usable:
                degraded.append(
                    f"required role '{status.role}' is unusable: "
                    f"{status.reason or 'unknown reason'}"
                )
            elif status.configured and status.served is False:
                degraded.append(
                    f"role '{status.role}' points at '{status.model}', which is not served"
                )

        payload["roles"] = [status.as_dict() for status in statuses]
        payload["problems"] = self._registry.configuration_problems()
        payload["ready"] = any_reachable and all(
            status.usable for status in statuses if status.required_for_demo
        )
        payload["degraded"] = degraded
        return payload


__all__ = ["HealthChecker", "ProviderHealth"]
