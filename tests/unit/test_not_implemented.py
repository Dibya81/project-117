"""Endpoints that are deliberately real-but-unbuilt (HTTP 501).

This file previously listed five endpoints as unimplemented. Four of them had
since been built and were returning real responses (or, in the case of
``POST /api/agents/run``, a 500 from an event-loop bug) — so the test was
pinning a stale picture of the API rather than a real contract, and it failed
the moment the endpoints landed.

Two things are asserted now:

1. the endpoints that genuinely still return 501 and carry a phase, and
2. that the endpoints which have been implemented no longer return 501, so
   the list cannot silently drift out of date again.
"""

from __future__ import annotations

import pytest

# (method, path, payload) — genuinely unbuilt: the route exists and answers
# with an explicit, phased 501 rather than a 404.
STILL_NOT_IMPLEMENTED: list[tuple[str, str, dict | None]] = [
    ("post", "/api/workflows/run", {"workflow": "report-generation", "inputs": {}}),
]

# Built since this file was written. Asserted as a *negative* contract: these
# must never regress to 501.
IMPLEMENTED: list[tuple[str, str, dict | None, int]] = [
    # Phase 12: creates a job and hands it to the orchestrator.
    ("post", "/api/agents/run", {"agent": "maintenance", "task": "inspect"}, 200),
    # Phase 8/9: unknown tool -> 404, bad arguments -> 400, needs approval -> 409.
    ("post", "/api/tools/execute", {"tool": "definitely-not-a-tool", "arguments": {}}, 404),
    # Phase 10: spec validation is a client error, not a server fault.
    ("post", "/api/artifacts/generate", {"kind": "pptx", "content": {}}, 400),
    ("get", "/api/artifacts/abc", None, 404),
]


@pytest.mark.parametrize("method,path,payload", STILL_NOT_IMPLEMENTED)
def test_endpoint_returns_explicit_not_implemented(client, method, path, payload):
    response = (
        getattr(client, method)(path, json=payload)
        if payload is not None
        else getattr(client, method)(path)
    )
    assert response.status_code == 501
    body = response.json()
    assert body["error"]["code"] == "not_implemented"
    assert body["error"]["phase"] is not None
    assert body["error"]["message"]


@pytest.mark.parametrize("method,path,payload,expected", IMPLEMENTED)
def test_implemented_endpoint_is_no_longer_501(client, method, path, payload, expected):
    response = (
        getattr(client, method)(path, json=payload)
        if payload is not None
        else getattr(client, method)(path)
    )
    assert response.status_code == expected, response.text
    assert response.status_code != 501, (
        f"{method.upper()} {path} regressed to 501 — it is implemented, so either "
        "the route broke or this file's IMPLEMENTED list is wrong"
    )
