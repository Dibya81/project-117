"""OpenAI-compatible provider.

Talks to ``{base_url}/chat/completions``, ``{base_url}/embeddings`` and
``{base_url}/models``. This single implementation serves Ollama's /v1 endpoint
and vLLM (and any other OpenAI-compatible local server), so switching local
backends is a configuration change.

Uses httpx directly (no SDK dependency) and accepts an optional
``httpx.MockTransport`` for tests.

From Phase 0.5 it also accepts an ``EgressPolicy``. Enforcement is installed
underneath the client as a transport, so chat, streaming, embeddings, model
listing and redirects are all covered by construction rather than by each
method remembering to check.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from backend.models.providers.base import (
    ChatMessage,
    ChatResult,
    ModelInfo,
    ProviderEgressBlocked,
    ProviderError,
    ProviderHttpError,
    ProviderUnreachable,
)
from backend.security.egress import EgressBlocked, EgressGuardTransport, EgressPolicy


def _message_text(message: dict[str, Any]) -> str:
    """Flatten a response message to text.

    Some OpenAI-compatible servers answer a content-parts request with
    content-parts rather than a bare string. Joining the text parts avoids
    handing a list back to callers typed for ``str``.
    """
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        )
    return "" if content is None else str(content)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    # Declares the *wire format* this provider can speak, not a promise that
    # any particular model can see. Ollama's /v1 endpoint and vLLM both accept
    # OpenAI content parts, so one implementation covers both. Picking an
    # image-capable model is the vision role's job (P117_VISION_MODEL); an
    # image sent to a text-only model fails loudly at the backend instead of
    # quietly returning a text-only guess.
    supports_images = True

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        egress: EgressPolicy | None = None,
    ) -> None:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        # Wrap the transport, not the calls: a new method added later cannot
        # bypass the policy by forgetting to consult it. `transport` stays
        # overridable so tests can inject httpx.MockTransport.
        if egress is not None:
            transport = EgressGuardTransport(egress, transport)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )

    # --- chat ------------------------------------------------------------

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        # Server-specific options (Ollama's ``keep_alive``/``think``). FastAPI's
        # OpenAI shim forwards unknown top-level fields to the native API, so
        # these reach the model server without a second code path. They are a
        # performance knob only — a server that ignores them still answers.
        if extra_body:
            payload.update(extra_body)
        data = await self._post_json("/chat/completions", payload)
        choice = data["choices"][0]
        return ChatResult(
            content=_message_text(choice["message"]),
            model=data.get("model", model),
            usage=data.get("usage") or {},
            finish_reason=choice.get("finish_reason"),
        )

    def chat_stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "stream": True,
        }

        async def _stream():
            try:
                async with self._client.stream(
                    "POST", "/chat/completions", json=payload
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        raise ProviderHttpError(f"chat stream failed: http {response.status_code}")
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except ValueError:
                            continue
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
            except ProviderHttpError:
                raise
            except EgressBlocked as exc:
                raise ProviderEgressBlocked(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise ProviderUnreachable(
                    f"cannot reach {self._client.base_url}: {exc.__class__.__name__}"
                ) from exc

        return _stream()

    async def chat_multimodal(
        self,
        *,
        model: str,
        prompt: str,
        images: list[str],
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """One text prompt plus one or more inlined images.

        Only ``data:`` URLs are accepted. An ``http(s)`` image URL would be
        dereferenced by the model server rather than by us, which would slip
        past ``EgressGuardTransport`` and quietly punch a hole in the egress
        policy. Refusing them keeps the sovereignty guarantee honest.
        """
        if not str(prompt or "").strip():
            raise ProviderError("chat_multimodal requires a non-empty prompt")
        if not images:
            raise ProviderError("chat_multimodal requires at least one image")

        parts: list[dict[str, Any]] = [{"type": "text", "text": str(prompt)}]
        for index, image in enumerate(images):
            reference = str(image or "").strip()
            if not reference:
                raise ProviderError(f"image {index} is empty")
            if not reference.startswith("data:"):
                raise ProviderError(
                    f"image {index} must be a data: URL — remote image URLs are "
                    "refused because the model server, not this client, would "
                    "fetch them and bypass the egress policy"
                )
            parts.append({"type": "image_url", "image_url": {"url": reference}})

        messages: list[dict[str, Any]] = []
        if system and str(system).strip():
            messages.append({"role": "system", "content": str(system)})
        messages.append({"role": "user", "content": parts})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        data = await self._post_json("/chat/completions", payload)
        return ChatResult(
            content=_message_text(data["choices"][0]["message"]),
            model=data.get("model", model),
            usage=data.get("usage") or {},
        )

    # --- embeddings ------------------------------------------------------

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        data = await self._post_json("/embeddings", {"model": model, "input": texts})
        return [item["embedding"] for item in data["data"]]

    # --- model discovery / health ---------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.get("/models")
        except EgressBlocked as exc:
            raise ProviderEgressBlocked(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnreachable(
                f"cannot reach {self._client.base_url}: {exc.__class__.__name__}"
            ) from exc
        if response.status_code != 200:
            raise ProviderHttpError(f"list models failed: http {response.status_code}")
        return [
            ModelInfo(id=item.get("id", ""), owned_by=item.get("owned_by", ""))
            for item in response.json().get("data", [])
        ]

    async def ping(self) -> bool:
        try:
            await self.list_models()
            return True
        except ProviderError:
            return False

    async def close(self) -> None:
        await self._client.aclose()

    # --- internals -------------------------------------------------------

    async def _post_json(self, path: str, payload: dict) -> dict:
        try:
            response = await self._client.post(path, json=payload)
        except EgressBlocked as exc:
            raise ProviderEgressBlocked(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnreachable(
                f"cannot reach {self._client.base_url}: {exc.__class__.__name__}"
            ) from exc
        if response.status_code != 200:
            raise ProviderHttpError(f"POST {path} failed: http {response.status_code}")
        return response.json()
