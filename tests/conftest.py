"""Shared test fixtures and doubles for the whole suite.

``FakeProvider`` lives here (not in ``tests/unit/conftest.py``) because it is
imported directly by test modules as ``from tests.conftest import
FakeProvider``. Defining it in the package root keeps that import stable
regardless of which subdirectory a test lives in.

The suite is also made *hermetic* below: it must describe a clean checkout on
every machine, and must not inherit a developer's local ``.env`` or exported
``P117_*`` variables.
"""

from __future__ import annotations

import os

from backend.config import Settings
from backend.models.providers.base import (
    ChatMessage,
    ChatResult,
    ModelInfo,
    ProviderUnreachable,
)

# --- hermetic environment -------------------------------------------------
# ``Settings`` reads ``.env`` from the process CWD and ``P117_*`` from the
# real environment. Running pytest from the repository root therefore picked
# up the local development ``.env``, which configured every model role and
# broke the assertions in tests/unit/test_model_config.py that pin the
# *unconfigured* defaults (a genuine failure: the checks are correct, the
# leaked configuration was not).
#
# Both sources are stripped here, at conftest import time, so the isolation
# applies before any test module is imported. Nothing in the application is
# changed: a real `uvicorn` run still resolves the root ``.env`` as documented.
for _key in [name for name in os.environ if name.startswith("P117_")]:
    del os.environ[_key]

Settings.model_config["env_file"] = None


class FakeProvider:
    """Deterministic in-process provider for API tests.

    ``chat`` echoes the last user message and reports how many messages the
    model actually received, so tests can observe history propagation.
    """

    name = "fake"

    def __init__(
        self,
        models: tuple[str, ...] = ("llama3:latest", "nomic-embed-text:latest"),
        fail_unreachable: bool = False,
    ) -> None:
        self.models = models
        self.fail_unreachable = fail_unreachable

    def _maybe_fail(self) -> None:
        if self.fail_unreachable:
            raise ProviderUnreachable("connection refused")

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        self._maybe_fail()
        last = messages[-1].content
        return ChatResult(
            content=f"n={len(messages)}:{last}",
            model=model,
            usage={"prompt_tokens": len(messages), "completion_tokens": 1},
        )

    def chat_stream(self, *, model: str, messages: list[ChatMessage], temperature: float = 0.2):
        self._maybe_fail()

        async def _gen():
            for part in ("hello ", "world"):
                yield part

        return _gen()

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2]] * len(texts)

    async def list_models(self) -> list[ModelInfo]:
        self._maybe_fail()
        return [ModelInfo(id=m) for m in self.models]

    async def ping(self) -> bool:
        try:
            self._maybe_fail()
            return True
        except ProviderUnreachable:
            return False

    async def close(self) -> None:
        pass
