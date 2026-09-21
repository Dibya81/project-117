from __future__ import annotations

import json

import httpx
import pytest
from backend.models.providers.base import ChatMessage, ProviderUnreachable
from backend.models.providers.openai_compatible import OpenAICompatibleProvider


def _transport_for(handler):
    return httpx.MockTransport(handler)


async def test_chat_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "llama3:latest"
        assert payload["messages"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "model": "llama3:latest",
                "choices": [{"message": {"role": "assistant", "content": "42"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1", transport=_transport_for(handler)
    )
    result = await provider.chat(
        model="llama3:latest",
        messages=[ChatMessage(role="user", content="2+2?")],
    )
    assert result.content == "42"
    assert result.model == "llama3:latest"
    assert result.usage["completion_tokens"] == 1


async def test_chat_stream_yields_tokens():
    sse = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            "data: [DONE]",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1", transport=_transport_for(handler)
    )
    tokens = []
    async for token in provider.chat_stream(
        model="llama3:latest", messages=[ChatMessage(role="user", content="hi")]
    ):
        tokens.append(token)
    assert tokens == ["hel", "lo"]


async def test_embed_parses_vectors():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
        )

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1", transport=_transport_for(handler)
    )
    vectors = await provider.embed(model="nomic-embed-text:latest", texts=["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_list_models_parses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "llama3:latest", "object": "model", "owned_by": "library"},
                    {"id": "nomic-embed-text:latest", "object": "model", "owned_by": "library"},
                ],
            },
        )

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1", transport=_transport_for(handler)
    )
    models = await provider.list_models()
    assert [m.id for m in models] == ["llama3:latest", "nomic-embed-text:latest"]


async def test_connection_error_maps_to_provider_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1", transport=_transport_for(handler)
    )
    with pytest.raises(ProviderUnreachable):
        await provider.list_models()
