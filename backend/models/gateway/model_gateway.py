"""Model gateway.

Owns the set of configured ``ModelProvider`` backends and exposes discovery +
health across all of them. The router (not the gateway) decides which
(provider, model) serves a role; callers ask for a role and never a concrete
backend.
"""

from __future__ import annotations

from typing import Any

from backend.models.providers.base import ModelInfo, ModelProvider


class ModelGateway:
    def __init__(
        self,
        providers: dict[str, ModelProvider],
        default_provider: str = "openai_compatible",
    ) -> None:
        if default_provider not in providers:
            raise ValueError(
                f"default_provider '{default_provider}' not among {sorted(providers)}"
            )
        self._providers = dict(providers)
        self._default = default_provider

    def provider(self, name: str | None = None) -> ModelProvider:
        return self._providers[name or self._default]

    def names(self) -> list[str]:
        return list(self._providers)

    async def list_models(self) -> dict[str, list[ModelInfo]]:
        result: dict[str, list[ModelInfo]] = {}
        for name, provider in self._providers.items():
            try:
                result[name] = await provider.list_models()
            except Exception:
                result[name] = []
        return result

    async def health(self) -> dict:
        """Degrades gracefully: a dead backend is reported, never fatal."""
        overall: dict[str, Any] = {"running": False}
        by_provider: dict[str, dict[str, bool]] = {}
        for name, provider in self._providers.items():
            ok = await provider.ping()
            by_provider[name] = {"running": ok}
            if ok:
                overall["running"] = True
        overall["providers"] = by_provider
        return overall

    async def close(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                pass