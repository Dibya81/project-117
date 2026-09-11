"""Fail-closed model configuration (Phase 0.5).

Three rules, each of which the code violated before this change:

1. Every role starts unconfigured. An unconfigured role produces a clear
   configuration error - never a silent fallback, never a download.
2. A Hugging Face repo id in any role is rejected AT STARTUP, because the
   first request would otherwise pull multi-GB weights off the public internet
   from a system whose entire claim is that nothing leaves the machine.
3. Reranking ships off, because every reranker backend we vendor is an HF path.

The old defaults (qwen3.5:9b, qwen3.5:4b, Qwen/Qwen3-Reranker-4B) contradicted
.env.example, which implied an unconfigured state. These tests pin the honest
behaviour so that divergence cannot come back.
"""

from __future__ import annotations

import pytest
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.router import ModelRouter, ModelUnavailableError
from pydantic import ValidationError

ALL_ROLES = ("reasoning", "vision", "embedding", "reranker", "coding", "domain")


def _settings(tmp_path, **overrides) -> Settings:
    values: dict = {
        "environment": "test",
        "database_url": f"sqlite:///{tmp_path / 'cfg.db'}",
        "uploads_dir": tmp_path / "uploads",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)


# --- defaults -------------------------------------------------------------


def test_every_role_defaults_to_unconfigured(tmp_path):
    settings = _settings(tmp_path)
    assert settings.reasoning_model == ""
    assert settings.vision_model == ""
    assert settings.embedding_model == ""
    assert settings.reranker_model == ""
    assert settings.coding_model == ""
    assert settings.domain_model == ""
    assert tuple(settings.unconfigured_roles()) == ALL_ROLES
    # ModelRoles must report absence, not an empty-string "model".
    assert ModelRoles(settings).all() == {}


def test_the_previously_hard_coded_defaults_are_gone(tmp_path):
    """Named regression: these three values risked a Hugging Face download."""
    settings = _settings(tmp_path)
    assert settings.reranker_model != "Qwen/Qwen3-Reranker-4B"
    assert settings.reasoning_model != "qwen3.5:9b"
    assert settings.domain_model != "qwen3.5:4b"


def test_reranking_is_disabled_by_default(tmp_path):
    assert _settings(tmp_path).retrieval_rerank_enabled is False


def test_sovereign_defaults_stay_on(tmp_path):
    settings = _settings(tmp_path)
    assert settings.egress_default_deny is True
    assert settings.allow_remote_model_repos is False


# --- the slash rule -------------------------------------------------------


@pytest.mark.parametrize(
    "role_field",
    ["reasoning_model", "embedding_model", "reranker_model", "coding_model"],
)
def test_remote_model_repos_are_rejected_at_startup(tmp_path, role_field):
    with pytest.raises(ValidationError) as excinfo:
        _settings(tmp_path, **{role_field: "Qwen/Qwen3-Reranker-4B"})
    message = str(excinfo.value)
    assert "zero-egress" in message
    assert "P117_ALLOW_REMOTE_MODEL_REPOS" in message
    # The error names the offending field, so the fix is obvious.
    assert role_field in message


def test_local_ollama_tags_are_accepted(tmp_path):
    """name:tag is local; only org/name implies a download."""
    settings = _settings(
        tmp_path,
        reasoning_model="qwen3.5:9b",
        embedding_model="nomic-embed-text:latest",
    )
    assert settings.reasoning_model == "qwen3.5:9b"
    assert settings.unconfigured_roles() == ["vision", "reranker", "coding", "domain"]


def test_remote_repo_requires_explicit_opt_in(tmp_path):
    settings = _settings(
        tmp_path,
        reranker_model="BAAI/bge-reranker-v2-m3",
        allow_remote_model_repos=True,
    )
    assert settings.reranker_model == "BAAI/bge-reranker-v2-m3"


# --- router behaviour -----------------------------------------------------


async def test_unconfigured_role_gives_a_configuration_error(fake_gateway, tmp_path):
    router = ModelRouter(fake_gateway, ModelRoles(_settings(tmp_path)), availability_ttl=0)
    with pytest.raises(ModelUnavailableError) as excinfo:
        await router.resolve("reasoning")
    message = str(excinfo.value)
    assert "no model is configured for role 'reasoning'" in message
    assert "P117_REASONING_MODEL" in message
    # It reports what IS served rather than guessing on the user's behalf.
    assert "llama3:latest" in excinfo.value.available_models


async def test_configured_but_unserved_model_is_never_swapped(fake_gateway, tmp_path):
    settings = _settings(tmp_path, reasoning_model="not-pulled:latest")
    router = ModelRouter(fake_gateway, ModelRoles(settings), availability_ttl=0)
    with pytest.raises(ModelUnavailableError) as excinfo:
        await router.resolve("reasoning")
    assert "not served by the local backend" in str(excinfo.value)


async def test_configured_and_served_model_resolves(fake_gateway, tmp_path):
    settings = _settings(tmp_path, reasoning_model="llama3:latest")
    router = ModelRouter(fake_gateway, ModelRoles(settings), availability_ttl=0)
    resolved = await router.resolve("reasoning")
    assert resolved.model == "llama3:latest"
    assert resolved.provider_name == "fake"


# --- host allowlist parsing ----------------------------------------------


def test_allowed_hosts_parse_from_a_comma_separated_string(tmp_path):
    settings = _settings(
        tmp_path, egress_allowed_hosts=" Historian.Plant.Local , dms.internal ,"
    )
    assert settings.egress_allowed_hosts == {"historian.plant.local", "dms.internal"}


def test_allowed_hosts_default_to_empty(tmp_path):
    assert _settings(tmp_path).egress_allowed_hosts == set()
