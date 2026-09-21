"""Shared fixtures for the simulation tests.

The recovery decision is produced by the three Project 117 agents over the
local model. Tests must not depend on a developer's Ollama install, so they
inject a fake model that returns a *valid* decision derived from the same
evidence the real model would see: the connection ids come straight out of the
evidence pack, never hardcoded.

A test that wants the genuine "LOCAL MODEL UNAVAILABLE" path clears the override
for its own scope.
"""

from __future__ import annotations

import json
import re

import pytest
from backend.simulation import decision


def _fake_ask(role: str, system: str, user: str) -> tuple[str, str]:
    """A test double that answers the three agents with a valid route.

    ``operations`` restores the first process line in the evidence pack. That
    line touches the incident scope by construction, so the recovery resolves
    and verification runs against real engine state. Nothing here knows a tag.
    """
    if role == "safety":
        return '{"safe": true, "concerns": []}', "test-model"
    if role == "diagnostic":
        return (
            '{"affected_equipment": [], "diagnosis": '
            '"measurement loss on the origin asset", "failure_mode": null}',
            "test-model",
        )
    # operations: the route is a real connection id from the evidence pack.
    # Take the LAST candidate, not the first: the evidence pack is ordered by the
    # plant graph, and the first line touching a two-hop incident scope is
    # `pl-001` for several different origins — which made two distinct incidents
    # look identical. The last candidate is still guaranteed to touch the scope
    # (the pack is filtered that way), and it differs with the incident.
    ids = list(dict.fromkeys(re.findall(r"pl-\d+", user)))[-1:]
    return (
        json.dumps(
            {
                "route": ids,
                "block": [],
                "restore": ids,
                "rationale": "restore process continuity along the affected lines",
            }
        ),
        "test-model",
    )


@pytest.fixture(autouse=True)
def _model_available(monkeypatch):
    """Every simulation test gets a working (fake) local model by default."""
    monkeypatch.setattr(decision, "_ask_override", _fake_ask)
    yield
