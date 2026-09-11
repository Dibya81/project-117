"""Model roles (Phase 2 — model gateway).

Application code must never hard-code model names. Everything asks for a role
(``reasoning``, ``vision``, ``embedding``, ``reranker``, ``coding``, ``domain``)
and the gateway resolves the configured model. Phase 2 adds the actual gateway
(Ollama → vLLM → other local backends); Phase 1 just centralizes the mapping.
"""

from __future__ import annotations

from backend.config import Settings


class ModelRoles:
    _ROLE_KEYS = (
        ("reasoning", "reasoning_model"),
        ("vision", "vision_model"),
        ("embedding", "embedding_model"),
        ("reranker", "reranker_model"),
        ("coding", "coding_model"),
        ("domain", "domain_model"),
    )

    def __init__(self, settings: Settings) -> None:
        self._roles: dict[str, str] = {
            role: getattr(settings, key)
            for role, key in self._ROLE_KEYS
            if getattr(settings, key)
        }

    def get(self, role: str) -> str | None:
        return self._roles.get(role)

    def all(self) -> dict[str, str]:
        return dict(self._roles)