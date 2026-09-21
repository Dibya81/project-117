"""Audit provenance columns (Phase 0.5).

An audit row must answer "who ran what, with which model, and who approved it"
on its own, without joining anything. Before this change ``AuditEvent`` could
record none of those four things - which would have made the Phase 7 approval
gates unauditable before they were even written.
"""

from __future__ import annotations

import pytest
from backend.security.audit import APPROVAL_STATES, AuditService


@pytest.fixture
def audit(client) -> AuditService:
    """Audit service on the app fixture's database (schema already created)."""
    return AuditService(client.app.state.session_factory)


def test_new_columns_default_honestly(audit):
    event = audit.record(action="document.uploaded", resource_type="document", resource_id="d1")
    assert event.agent is None
    assert event.tool is None
    assert event.model is None
    # Never "approved" by default: that would forge consent nobody gave.
    assert event.approval == "not_required"


def test_provenance_round_trips(audit):
    event = audit.record(
        action="tool.executed",
        resource_type="job",
        resource_id="job-1",
        user="operator@plant",
        agent="maintenance",
        tool="run_python",
        model="qwen3.5:9b",
        approval="approved",
        detail={"duration_ms": 812},
    )
    stored = audit.get(event.id)
    assert stored is not None
    assert stored.agent == "maintenance"
    assert stored.tool == "run_python"
    assert stored.model == "qwen3.5:9b"
    assert stored.approval == "approved"
    assert stored.user == "operator@plant"


def test_filters_answer_the_questions_an_auditor_asks(audit):
    audit.record(
        action="tool.executed",
        agent="maintenance",
        tool="run_python",
        approval="approved",
    )
    audit.record(
        action="tool.executed",
        agent="documentation",
        tool="create_pptx",
        approval="pending",
    )
    audit.record(action="search.performed")

    assert len(audit.list(tool="run_python")) == 1
    assert len(audit.list(agent="documentation")) == 1
    # "What is waiting on a human right now?"
    assert [e.tool for e in audit.list(approval="pending")] == ["create_pptx"]
    assert len(audit.list(approval="not_required")) == 1


def test_unknown_approval_state_is_refused(audit):
    """A typo must not be able to record an operation as authorised."""
    with pytest.raises(ValueError, match="unknown approval state"):
        audit.record(action="tool.executed", approval="totally-fine")
    assert APPROVAL_STATES == {"not_required", "pending", "approved", "rejected"}


def test_api_exposes_provenance_fields(client):
    upload = client.post(
        "/api/documents/upload",
        files={"files": ("provenance.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload.status_code == 201
    body = client.get("/api/audit", params={"action": "document.uploaded"}).json()
    event = body["events"][0]
    assert event["approval"] == "not_required"
    assert event["agent"] is None
    assert event["tool"] is None
    assert event["model"] is None


def test_api_can_filter_by_approval(client):
    audit = AuditService(client.app.state.session_factory)
    audit.record(action="tool.executed", tool="run_shell", approval="pending")
    body = client.get("/api/audit", params={"approval": "pending"}).json()
    assert body["total"] == 1
    assert body["events"][0]["tool"] == "run_shell"
