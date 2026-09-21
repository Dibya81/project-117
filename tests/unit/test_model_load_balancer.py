"""Unit tests for multi-provider ModelRouter and LoadBalancer integration."""

from __future__ import annotations

import pytest
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.gateway.load_balancer import ROUND_ROBIN, LoadBalancer
from backend.models.providers.base import ModelInfo, ModelProvider
from backend.models.router import ModelRouter


class FakeProvider(ModelProvider):
    def __init__(self, name: str, models: list[str]) -> None:
        self._name = name
        self._models = [ModelInfo(id=m, name=m, provider=name) for m in models]

    async def list_models(self) -> list[ModelInfo]:
        return self._models

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_router_load_balancing_multiple_providers() -> None:
    p1 = FakeProvider("primary", ["qwen3:8b", "llama3.2:3b"])
    p2 = FakeProvider("replica", ["qwen3:8b"])

    gateway = ModelGateway(
        providers={"primary": p1, "replica": p2},
        default_provider="primary",
    )
    settings = Settings(
        reasoning_model="qwen3:8b",
        vision_model="llama3.2:3b",
    )
    roles = ModelRoles(settings)
    lb = LoadBalancer(strategy=ROUND_ROBIN)
    router = ModelRouter(gateway, roles, availability_ttl=10.0, load_balancer=lb)

    # First resolution chooses one candidate
    res1 = await router.resolve("reasoning")
    # Second resolution with round robin chooses the other candidate
    res2 = await router.resolve("reasoning")

    chosen = {res1.provider_name, res2.provider_name}
    assert chosen == {"primary", "replica"}

    # Model available only on primary
    res_vision = await router.resolve("vision")
    assert res_vision.provider_name == "primary"
