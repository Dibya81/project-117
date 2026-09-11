from __future__ import annotations

from backend.security.egress import EgressPolicy


def test_default_deny_blocks_external_hosts():
    policy = EgressPolicy(default_deny=True)
    assert not policy.allows("https://example.com/api")
    assert not policy.allows("http://169.254.169.254/latest/meta-data")  # cloud metadata
    assert not policy.allows("ftp://example.com/file")
    assert not policy.allows("file:///etc/passwd")


def test_local_model_endpoints_always_allowed():
    policy = EgressPolicy(default_deny=True)
    assert policy.allows("http://localhost:11434/api/tags")  # Ollama
    assert policy.allows("http://127.0.0.1:8080")  # OpenSandbox


def test_allowlist_permits_only_listed_hosts():
    policy = EgressPolicy(default_deny=True).with_allowlist("internal.historian.local")
    assert policy.allows("https://internal.historian.local/api")
    assert not policy.allows("https://external.historian.local/api")


def test_non_deny_mode_still_restricts_schemes():
    policy = EgressPolicy(default_deny=False)
    assert policy.allows("https://anything.example")
    assert not policy.allows("file:///etc/shadow")
    assert not policy.allows("gopher://example.com")