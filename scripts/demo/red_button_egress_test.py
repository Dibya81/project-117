#!/usr/bin/env python3
"""Zero-Egress / Red-Button Network Security Demo.

Demonstrates:
1. Zero-egress policy active by default (`P117_EGRESS_DEFAULT_DENY=true`).
2. Permitted on-premise local endpoints (loopback, local Ollama, internal backend).
3. Immediate structural blocking of external outbound traffic (e.g. OpenAI, telemetry).
4. Verified `EgressBlocked` exception raised at transport level.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx  # noqa: E402
from backend.security.egress import (  # noqa: E402
    EgressBlocked,
    EgressGuardSyncTransport,
    EgressPolicy,
)


def main() -> int:
    print("=" * 70)
    print("Project 117 — Sovereign Zero-Egress Enforcement Test")
    print("=" * 70)

    policy = EgressPolicy(default_deny=True)
    guard = EgressGuardSyncTransport(policy=policy)

    print("\n[Step 1] Verifying Zero-Egress Default Policy Configuration...")
    print(f"  ✓ Default Deny: {policy.default_deny}")
    print(f"  ✓ Allowed Loopback Hosts: {sorted(list(policy._LOCAL_HOSTS))}")
    print(f"  ✓ Allowed External Hosts: {sorted(list(policy.allowed_hosts)) or 'None (Zero External Egress)'}")

    print("\n[Step 2] Testing permitted local loopback destinations...")
    test_local_urls = [
        "http://127.0.0.1:8000/health",
        "http://localhost:11434/api/tags",
        "http://[::1]:8080/status",
    ]
    for url in test_local_urls:
        allowed = policy.allows(url)
        print(f"  ✓ Destination: {url:<40} -> Allowed: {allowed}")
        assert allowed, f"Local destination {url} should be allowed!"

    print("\n[Step 3] Testing blocked external internet destinations...")
    test_external_urls = [
        "https://api.openai.com/v1/chat/completions",
        "https://api.anthropic.com/v1/messages",
        "http://telemetry.external-cloud.com/collect",
        "https://huggingface.co/models",
    ]

    for url in test_external_urls:
        allowed = policy.allows(url)
        print(f"  ⚡ Destination: {url:<45} -> Policy allows: {allowed}")
        assert not allowed, f"External destination {url} must be denied by zero-egress policy!"

    print("\n[Step 4] Live transport interception test via EgressGuardSyncTransport...")
    with httpx.Client(transport=guard) as client:
        for url in test_external_urls:
            try:
                print(f"  Attempting HTTP request to {url} ...")
                client.get(url, timeout=2.0)
                print(f"  ✗ FAILED: Connection to {url} was NOT blocked!")
                return 1
            except EgressBlocked as exc:
                print(f"  ✓ BLOCKED AT TRANSPORT GATE: {exc}")

    print("\n" + "=" * 70)
    print("Demo complete: Sovereign Zero-Egress posture is structurally enforced.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
