"""Provider contracts + shared error types.

Every local model backend (Ollama, vLLM, llama.cpp, …) implements
``ModelProvider``. Application code never talks to a backend directly — it goes
through the model router/gateway, which resolve a *role* to a concrete
(provider, model) pair from configuration.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # system | user | assistant
    content: str


class ChatResult(BaseModel):
    content: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    #: Why the server stopped. ``"length"`` means the reply was cut off by the
    #: token budget (so ``content`` can legitimately be empty when the model was
    #: still reasoning), which is a different failure from an empty answer and
    #: must not be retried identically.
    finish_reason: str | None = None


class ModelInfo(BaseModel):
    id: str
    owned_by: str = ""


class ProviderError(Exception):
    """Base for provider failures; carries a stable code."""

    code = "provider_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderUnreachable(ProviderError):
    """The backend could not be reached (down, wrong URL, timeout)."""

    code = "provider_unreachable"


class ProviderHttpError(ProviderError):
    """The backend answered with a non-2xx status."""

    code = "provider_http_error"


class ProviderEgressBlocked(ProviderError):
    """The egress policy refused the request; the network was never touched.

    Deliberately distinct from ``ProviderUnreachable``. Reporting a
    sovereignty violation as "the backend is down" would hide it from the
    operator, who needs to know that something tried to leave the machine.
    """

    code = "egress_blocked"


class ModelProvider(Protocol):
    name: str

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatResult: ...

    def chat_stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
    ) -> AsyncIterator[str]: ...

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]: ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class MultimodalProvider(Protocol):
    """Optional capability: accepting images alongside a text prompt.

    Deliberately a *separate* protocol rather than extra members on
    ``ModelProvider``. A text-only backend is a perfectly valid provider, so
    image support has to be something callers discover, not something every
    implementation is forced to fake. Use :func:`supports_images` to probe
    before reaching for ``chat_multimodal``.

    ``images`` are RFC 2397 data URLs. Remote ``http(s)`` image references are
    refused by implementations on purpose: the *model server* would be the one
    fetching them, which slips past ``EgressGuardTransport`` (that guards our
    own client, not the backend's). Inlining the bytes keeps every byte we
    send accounted for.
    """

    supports_images: bool

    async def chat_multimodal(
        self,
        *,
        model: str,
        prompt: str,
        images: list[str],
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult: ...


def supports_images(provider: object) -> bool:
    """Single canonical probe for image capability.

    Requires both the flag *and* the method, so a provider that advertises
    the capability without implementing it is treated as text-only instead of
    failing later with ``AttributeError`` mid-request.
    """
    return bool(getattr(provider, "supports_images", False)) and callable(
        getattr(provider, "chat_multimodal", None)
    )
