"""Model router.

Resolves a *role* (``reasoning``, ``vision``, ``embedding``, ``reranker``,
``coding``, ``domain``) or an explicit model name to a concrete
``ResolvedModel`` backed by a live provider. Availability is verified against
the provider's model list (cached with a TTL); a missing/unconfigured model is
a loud, typed error — never a silent swap to something else.
"""

from __future__ import annotations

import threading
import time

from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.gateway.load_balancer import LoadBalancer
from backend.models.providers.base import (
    ModelProvider,
    ProviderHttpError,
    ProviderUnreachable,
)


class ModelUnavailableError(Exception):
    """The role has no configured model, or the model is not served locally."""

    def __init__(self, message: str, available_models: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.available_models = available_models or []


class ResolvedModel:
    def __init__(self, provider_name: str, model: str, provider: ModelProvider) -> None:
        self.provider_name = provider_name
        self.model = model
        self.provider = provider

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ResolvedModel({self.provider_name}/{self.model})"


class ModelRouter:
    _ROLES = ("reasoning", "vision", "embedding", "reranker", "coding", "domain")

    def __init__(
        self,
        gateway: ModelGateway,
        roles: ModelRoles,
        availability_ttl: float = 60.0,
        load_balancer: LoadBalancer | None = None,
    ) -> None:
        self._gateway = gateway
        self._roles = roles
        self._ttl = availability_ttl
        self._load_balancer = load_balancer or LoadBalancer()
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, frozenset[str]]] = {}

    def known_roles(self) -> tuple[str, ...]:
        return self._ROLES

    def role_mapping(self) -> dict[str, str | None]:
        return {role: self._roles.get(role) for role in self._ROLES}

    async def resolve(self, role: str, *, model_override: str | None = None) -> ResolvedModel:
        if role not in self._ROLES:
            raise ValueError(f"unknown model role '{role}' (known: {', '.join(self._ROLES)})")

        names = self._gateway.names()
        if not names:
            raise ModelUnavailableError("no model provider is configured")

        model = (model_override or self._roles.get(role) or "").strip()
        if not model:
            first_avail = list(await self._available_models(names[0])) if names else []
            raise ModelUnavailableError(
                f"no model is configured for role '{role}' — set "
                f"P117_{role.upper()}_MODEL (see .env.example)",
                available_models=first_avail,
            )

        candidates: list[str] = []
        all_available: set[str] = set()
        for p_name in names:
            try:
                avail = await self._available_models(p_name)
                all_available.update(avail)
                if model in avail:
                    candidates.append(p_name)
            except (ProviderUnreachable, ProviderHttpError):
                if len(names) == 1:
                    raise
                continue
            except Exception:
                continue

        if not candidates:
            raise ModelUnavailableError(
                f"model '{model}' (role '{role}') is not served by the local backend — "
                f"check `ollama list` / GET /api/models",
                available_models=sorted(all_available),
            )

        chosen_provider = self._load_balancer.choose(candidates)
        return ResolvedModel(
            provider_name=chosen_provider,
            model=model,
            provider=self._gateway.provider(chosen_provider),
        )

    async def _available_models(self, provider_name: str) -> frozenset[str]:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(provider_name)
            if cached and now - cached[0] < self._ttl:
                return cached[1]

        provider = self._gateway.provider(provider_name)
        try:
            models = frozenset(info.id for info in await provider.list_models())
        except (ProviderUnreachable, ProviderHttpError):
            # A down backend must surface as "provider unreachable", never as
            # a confusing "model missing" error.
            raise
        except Exception:  # pragma: no cover - defensive
            models = frozenset()
        with self._lock:
            self._cache[provider_name] = (now, models)
        return models
