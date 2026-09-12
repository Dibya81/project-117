"""Egress ENFORCEMENT tests (Phase 0.5).

``test_egress.py`` proves the policy *decides* correctly. These tests prove the
decision is actually *enforced* on outbound HTTP - the precise gap the Phase 0
audit found, where ``EgressPolicy`` existed, had passing unit tests, and was
consulted by no HTTP client whatsoever.

The regression being locked down: someone builds an ``httpx.AsyncClient``
directly, or the app stops wiring the guard, and confidential document content
silently gains a route off the machine.
"""

from __future__ import annotations

import httpx
import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.models.providers.base import ChatMessage, ProviderEgressBlocked
from backend.models.providers.openai_compatible import OpenAICompatibleProvider
from backend.security.egress import (
    EgressBlocked,
    EgressGuardSyncTransport,
    EgressGuardTransport,
    EgressPolicy,
    guarded_async_client,
    policy_from_settings,
)

DENY = EgressPolicy(default_deny=True)


def _would_let_it_out(request: httpx.Request) -> httpx.Response:
    """Inner transport that would happily send the request.

    Using a permissive inner transport matters: every assertion below is then
    about the guard, not about the request failing for some other reason.
    """
    return httpx.Response(200, json={"reached": True})


def _guarded(policy: EgressPolicy = DENY) -> EgressGuardTransport:
    return EgressGuardTransport(policy, httpx.MockTransport(_would_let_it_out))


# --- transport level ------------------------------------------------------


async def test_external_host_is_blocked():
    async with httpx.AsyncClient(transport=_guarded()) as client:
        with pytest.raises(EgressBlocked) as excinfo:
            await client.get("https://api.openai.com/v1/models")
    assert excinfo.value.host == "api.openai.com"


async def test_blocked_request_never_reaches_the_inner_transport():
    """Prevention, not detection: the payload must never be handed onward."""
    attempted: list[str] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        attempted.append(str(request.url))
        return httpx.Response(200)

    transport = EgressGuardTransport(DENY, httpx.MockTransport(recording_handler))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(EgressBlocked):
            await client.post("https://example.com/ingest", json={"page": "confidential"})
    assert attempted == []


async def test_local_model_and_sandbox_endpoints_stay_reachable():
    async with httpx.AsyncClient(transport=_guarded()) as client:
        for url in (
            "http://localhost:11434/v1/models",  # Ollama
            "http://127.0.0.1:8080/v1/sandboxes",  # OpenSandbox
        ):
            response = await client.get(url)
            assert response.json() == {"reached": True}, url


async def test_cloud_metadata_service_is_blocked():
    async with httpx.AsyncClient(transport=_guarded()) as client:
        with pytest.raises(EgressBlocked):
            await client.get("http://169.254.169.254/latest/meta-data/iam/")


async def test_allowlist_permits_only_the_named_internal_host():
    transport = _guarded(DENY.with_allowlist("historian.plant.local"))
    async with httpx.AsyncClient(transport=transport) as client:
        allowed = await client.get("https://historian.plant.local/api/tags")
        assert allowed.status_code == 200
        with pytest.raises(EgressBlocked):
            await client.get("https://historian.plant.example/api/tags")


def test_sync_transport_enforces_too():
    transport = EgressGuardSyncTransport(DENY, httpx.MockTransport(_would_let_it_out))
    with httpx.Client(transport=transport) as client:
        assert client.get("http://127.0.0.1:11434/v1/models").status_code == 200
        with pytest.raises(EgressBlocked):
            client.get("https://huggingface.co/api/models")


async def test_guarded_client_helper_is_policed():
    client = guarded_async_client(
        policy=DENY,
        base_url="https://api.anthropic.com",
        transport=httpx.MockTransport(_would_let_it_out),
    )
    try:
        with pytest.raises(EgressBlocked):
            await client.get("/v1/messages")
    finally:
        await client.aclose()


# --- provider level -------------------------------------------------------


async def test_provider_reports_a_block_as_egress_not_as_downtime():
    """A blocked call is a policy event, not an outage - and must read as one."""
    provider = OpenAICompatibleProvider(
        "https://api.openai.com/v1",
        transport=httpx.MockTransport(_would_let_it_out),
        egress=DENY,
    )
    try:
        with pytest.raises(ProviderEgressBlocked) as excinfo:
            await provider.list_models()
        assert excinfo.value.code == "egress_blocked"

        with pytest.raises(ProviderEgressBlocked):
            await provider.chat(
                model="gpt-4", messages=[ChatMessage(role="user", content="hi")]
            )
        with pytest.raises(ProviderEgressBlocked):
            await provider.embed(model="text-embedding-3", texts=["confidential"])
        with pytest.raises(ProviderEgressBlocked):
            async for _ in provider.chat_stream(
                model="gpt-4", messages=[ChatMessage(role="user", content="hi")]
            ):
                pass
    finally:
        await provider.close()


async def test_local_provider_still_works_with_the_policy_attached():
    """Enforcement must not make the legitimate local path harder."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"id": "llama3:latest", "owned_by": "library"}]}
        )

    provider = OpenAICompatibleProvider(
        "http://localhost:11434/v1",
        transport=httpx.MockTransport(handler),
        egress=DENY,
    )
    try:
        assert [m.id for m in await provider.list_models()] == ["llama3:latest"]
    finally:
        await provider.close()


# --- wiring ---------------------------------------------------------------


def _settings(tmp_path, **overrides) -> Settings:
    values: dict = {
        "environment": "test",
        "database_url": f"sqlite:///{tmp_path / 'egress.db'}",
        "uploads_dir": tmp_path / "uploads",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)


def test_app_actually_installs_the_guard(tmp_path):
    """The audit finding itself: policy present, enforcement absent.

    Asserting on the client's transport is intentionally invasive. A test that
    only checked ``app.state.egress`` would have passed before this change,
    while every outbound request still escaped.
    """
    app = create_app(_settings(tmp_path))
    provider = app.state.gateway.provider()
    assert isinstance(provider._client._transport, EgressGuardTransport)
    assert app.state.egress.default_deny is True


def test_policy_is_built_from_settings(tmp_path):
    settings = _settings(
        tmp_path, egress_allowed_hosts="Historian.Plant.Local, dms.internal"
    )
    policy = policy_from_settings(settings)
    assert policy.allows("https://historian.plant.local/api")  # case-insensitive
    assert policy.allows("https://dms.internal/api")
    assert not policy.allows("https://api.openai.com/v1/chat/completions")


# --- observation -----------------------------------------------------------
#
# Enforcement without observation is still unverifiable: the Security view says
# "external calls: 0" and there is no way to tell a quiet machine from a monitor
# nobody feeds. These tests pin the wiring from the guard transport to the
# process monitor, and pin the loopback/external split - counting our own Ollama
# traffic as "external" would inflate the exact number that proves the
# sovereignty claim.


@pytest.fixture()
def clean_monitor():
    from backend.security.network import network_monitor

    network_monitor.MONITOR.reset()
    yield network_monitor.MONITOR
    network_monitor.MONITOR.reset()


async def test_guard_records_blocked_external_attempts(clean_monitor):
    async with httpx.AsyncClient(transport=_guarded()) as client:
        with pytest.raises(EgressBlocked):
            await client.get("https://api.openai.com/v1/models")

    assert clean_monitor.totals()["external_blocked"] == 1
    assert clean_monitor.totals()["external_allowed"] == 0
    assert "api.openai.com" in clean_monitor.summary()["blocked_hosts"]


async def test_local_traffic_is_not_counted_as_external(clean_monitor):
    async with httpx.AsyncClient(transport=_guarded()) as client:
        await client.get("http://127.0.0.1:11434/v1/models")
        await client.get("http://localhost:11434/v1/models")

    totals = clean_monitor.totals()
    assert totals["local_allowed"] == 2
    assert totals["external_allowed"] == 0
    assert clean_monitor.summary()["external_allowed"] == 0


def test_sync_guard_records_local_and_external(clean_monitor):
    transport = EgressGuardSyncTransport(DENY, httpx.MockTransport(_would_let_it_out))
    with httpx.Client(transport=transport) as client:
        assert client.get("http://127.0.0.1:11434/v1/models").status_code == 200
        with pytest.raises(EgressBlocked):
            client.get("https://huggingface.co/api/models")

    totals = clean_monitor.totals()
    assert totals["local_allowed"] == 1
    assert totals["external_blocked"] == 1
    assert totals["external_allowed"] == 0


def test_health_reports_real_egress_counts(client, clean_monitor):
    """The false-zero regression: a monitor nobody feeds reads as a clean machine.

    Deltas rather than absolutes, because the health probe itself reaches Ollama
    over loopback and that call is legitimately recorded.
    """
    from backend.security.network.network_monitor import record_decision

    first = client.get("/health").json()["network"]

    record_decision(
        host="api.openai.com", scheme="https", decision="blocked", local=False
    )
    record_decision(host="127.0.0.1", scheme="http", decision="allowed", local=True)

    second = client.get("/health").json()["network"]
    assert second["external_blocked"] == first["external_blocked"] + 1
    # Loopback traffic must never be promoted into the external figure.
    assert second["external_allowed"] == first["external_allowed"]
    assert second["totals"]["local_allowed"] > first["totals"]["local_allowed"]
    assert second["scope"] == "this process only"
