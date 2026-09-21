"""Contract tests for the ``/api/v1`` mobile field API.

These pin the *wire contract*, not just the status codes: every payload is
compared field-for-field against the frozen Android DTOs
(``apps/mobile/.../dto/Dtos.kt``). A wrong or missing key is a runtime failure
on the phone, so it has to be a test failure here.

The fixture is hermetic: its own identity/mobile/operations databases, its own
minimal simulation database (one real agent task), and an injected fake model
provider so ``/chat`` does not need a local LLM.
"""

from __future__ import annotations

import sqlite3

import pytest
from backend.api.src.main import create_app
from backend.chat.service import ChatService
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.router import ModelRouter
from fastapi.testclient import TestClient

from tests.conftest import FakeProvider

SUPERVISOR = ("supervisor", "Demo-Supervisor-117!")
TECHNICIAN = ("technician", "Demo-Technician-117!")

# ─── Expected DTO field sets (frozen client contract) ─────────────────────────
EQUIPMENT_KEYS = {
    "id",
    "name",
    "type",
    "location",
    "status",
    "qr_code",
    "barcode",
    "manufacturer",
    "model",
    "serial_number",
    "last_maintenance_date",
    "next_maintenance_date",
    "metadata",
    "readings",
}
WORK_ORDER_KEYS = {
    "id",
    "title",
    "description",
    "status",
    "priority",
    "assigned_to",
    "equipment_id",
    "equipment_name",
    "due_date",
    "created_at",
    "updated_at",
    "steps",
    "issue_id",
    "notes",
}
APPROVAL_KEYS = {
    "id",
    "title",
    "description",
    "work_order_id",
    "work_order_title",
    "equipment_id",
    "equipment_name",
    "consequence",
    "requested_by",
    "requested_at",
    "deadline",
    "status",
}
AGENT_TASK_KEYS = {
    "id",
    "title",
    "description",
    "source",
    "priority",
    "status",
    "equipment_id",
    "equipment_name",
    "work_order_id",
    "instructions",
    "evidence_required",
    "due_by",
    "created_at",
}
NOTIFICATION_KEYS = {
    "id",
    "type",
    "title",
    "body",
    "timestamp",
    "is_read",
    "reference_id",
    "reference_type",
}
ISSUE_KEYS = {
    "id",
    "equipment_id",
    "equipment_name",
    "description",
    "severity",
    "reported_by",
    "reported_at",
    "work_order_id",
}
SOP_KEYS = {
    "id",
    "title",
    "category",
    "version",
    "summary",
    "content",
    "equipment_types",
    "tags",
    "last_updated",
}
LOGIN_KEYS = {
    "access_token",
    "refresh_token",
    "user_id",
    "username",
    "display_name",
    "role",
    "permissions",
}
ME_KEYS = {"user_id", "username", "display_name", "role", "permissions"}


def _make_simulation_db(path) -> str:
    """A minimal engine database holding one real agent task and its incident."""
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE incidents (
            id TEXT PRIMARY KEY, plant_id TEXT, title TEXT, severity TEXT, status TEXT,
            origin_equipment TEXT, origin_sensor TEXT, failure_mode TEXT, affected TEXT,
            fault_event_id TEXT, created_at REAL, resolved_at REAL, wall_created REAL,
            wall_updated REAL
        );
        CREATE TABLE agent_tasks (
            id TEXT PRIMARY KEY, execution_id TEXT, incident_id TEXT, agent TEXT, title TEXT,
            status TEXT, sequence INTEGER, depends_on TEXT, tools TEXT, result TEXT,
            started_at REAL, completed_at REAL, wall_ts REAL
        );
        CREATE TABLE agent_evidence (
            id TEXT PRIMARY KEY, task_id TEXT, incident_id TEXT, source_type TEXT,
            source_id TEXT, description TEXT, confidence REAL, citation TEXT, wall_ts REAL
        );
        INSERT INTO incidents VALUES
            ('INC-T1','refinery','Test incident','critical','resolved','e-P-1042',NULL,
             NULL,'[]',NULL,0.0,0.0,1700000000.0,1700000000.0);
        INSERT INTO agent_tasks VALUES
            ('INC-T1-1','EXEC-T1','INC-T1','maintenance','Inspect the pump','completed',1,
             '[]','[]','Bearing wear confirmed.',0.0,1.0,1700000000.0);
        INSERT INTO agent_evidence VALUES
            ('EV-1','INC-T1-1','INC-T1','telemetry','s-1','vibration high',0.9,NULL,1700000000.0);
        """
    )
    connection.commit()
    connection.close()
    return str(path)


@pytest.fixture
def mobile_client(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        uploads_dir=tmp_path / "uploads",
        identity_db=tmp_path / "identity.db",
        mobile_db=tmp_path / "mobile.db",
        operations_db=tmp_path / "operations.db",
        materials_db=tmp_path / "materials.db",
        simulation_db=tmp_path / "simulation.db",
        lancedb_dir=tmp_path / "lancedb",
        simulation_enabled=False,
        reasoning_model="llama3:latest",
        llm_base_url="http://127.0.0.1:1/v1",
        log_level="ERROR",
    )
    _make_simulation_db(settings.simulation_db)
    app = create_app(settings)
    fake_gateway = ModelGateway(providers={"fake": FakeProvider()}, default_provider="fake")
    app.state.gateway = fake_gateway
    app.state.router = ModelRouter(fake_gateway, ModelRoles(settings), availability_ttl=0)
    app.state.chat = ChatService(
        app.state.router, app.state.sessions, app.state.audit, retrieval=None
    )
    with TestClient(app) as client:
        yield client


def _login(client, account=SUPERVISOR) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": account[0], "password": account[1], "device_token": ""},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['access_token']}"}


def _first_equipment(client, headers) -> dict:
    response = client.get("/api/v1/equipment", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "the real plant dataset should expose at least one asset"
    return items[0]


# ─── Auth ─────────────────────────────────────────────────────────────────────
def test_health_is_public(mobile_client):
    response = mobile_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_response_matches_dto(mobile_client):
    body = _login(mobile_client)
    assert set(body) == LOGIN_KEYS
    assert body["role"] == "SUPERVISOR"
    assert body["username"] == "supervisor"
    # The phone checks these exact grant strings (Models.kt::Permissions).
    assert "approvals:decide" in body["permissions"]
    assert "equipment:view" in body["permissions"]


def test_login_rejects_bad_password(mobile_client):
    response = mobile_client.post(
        "/api/v1/auth/login",
        json={"username": "supervisor", "password": "wrong", "device_token": ""},
    )
    assert response.status_code == 401


def test_protected_route_without_token_is_401(mobile_client):
    assert mobile_client.get("/api/v1/equipment").status_code == 401
    assert mobile_client.get("/api/v1/work-orders").status_code == 401
    assert mobile_client.get("/api/v1/notifications").status_code == 401


def test_protected_route_with_invalid_token_is_401(mobile_client):
    response = mobile_client.get(
        "/api/v1/equipment", headers={"Authorization": "Bearer p117a.not.a.token"}
    )
    assert response.status_code == 401


def test_me_matches_dto(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    response = mobile_client.get("/api/v1/auth/me", headers=_auth(session))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == ME_KEYS
    assert body["role"] == "TECHNICIAN"


def test_enroll_login_refresh_logout(mobile_client):
    enroll = mobile_client.post(
        "/api/v1/auth/enroll",
        json={"device_id": "test-device-1", "enrollment_code": "ENROLL-2026-X9"},
    )
    assert enroll.status_code == 200
    assert set(enroll.json()) == {"enrolled", "device_token"}
    assert enroll.json()["enrolled"] is True

    login = mobile_client.post(
        "/api/v1/auth/login",
        json={
            "username": TECHNICIAN[0],
            "password": TECHNICIAN[1],
            "device_token": enroll.json()["device_token"],
        },
    )
    assert login.status_code == 200
    session = login.json()

    refreshed = mobile_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert set(refreshed.json()) == {"access_token"}
    assert (
        mobile_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
        ).status_code
        == 200
    )

    assert mobile_client.post("/api/v1/auth/logout", headers=_auth(session)).status_code == 200
    # After logout the refresh token is dead...
    assert (
        mobile_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).status_code
        == 401
    )
    # ...and so is the access token: the session row is revoked.
    assert mobile_client.get("/api/v1/auth/me", headers=_auth(session)).status_code == 401


def test_bad_enrollment_code_is_401(mobile_client):
    response = mobile_client.post(
        "/api/v1/auth/enroll",
        json={"device_id": "d", "enrollment_code": "NOPE"},
    )
    assert response.status_code == 401


# ─── Equipment ────────────────────────────────────────────────────────────────
def test_equipment_list_matches_dto(mobile_client):
    session = _login(mobile_client)
    response = mobile_client.get("/api/v1/equipment", headers=_auth(session))
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    for item in items:
        assert set(item) == EQUIPMENT_KEYS


def test_equipment_detail_and_identify(mobile_client):
    session = _login(mobile_client)
    headers = _auth(session)
    first = _first_equipment(mobile_client, headers)

    detail = mobile_client.get(f"/api/v1/equipment/{first['id']}", headers=headers)
    assert detail.status_code == 200
    assert set(detail.json()) == EQUIPMENT_KEYS

    assert first["qr_code"], "each asset should expose its real plant tag as qr_code"
    identified = mobile_client.post(
        "/api/v1/equipment/identify", json={"qr_code": first["qr_code"]}, headers=headers
    )
    assert identified.status_code == 200
    assert identified.json()["id"] == first["id"]

    assert (
        mobile_client.post(
            "/api/v1/equipment/identify", json={"qr_code": "no-such-tag"}, headers=headers
        ).status_code
        == 404
    )


# ─── Work orders ──────────────────────────────────────────────────────────────
def _create_work_order(mobile_client, equipment_id: str) -> str:
    response = mobile_client.post(
        "/api/work-orders",
        json={
            "title": "Mobile contract test work order",
            "equipmentId": equipment_id,
            "priority": "high",
            "status": "open",
            "description": "Created by the test suite.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["workOrder"]["id"]


def test_work_order_list_detail_and_update(mobile_client):
    session = _login(mobile_client)
    headers = _auth(session)
    equipment = _first_equipment(mobile_client, headers)
    work_order_id = _create_work_order(mobile_client, equipment["id"])

    listing = mobile_client.get("/api/v1/work-orders", headers=headers)
    assert listing.status_code == 200
    assert set(listing.json()) == {"items"}
    for item in listing.json()["items"]:
        assert set(item) == WORK_ORDER_KEYS

    detail = mobile_client.get(f"/api/v1/work-orders/{work_order_id}", headers=headers)
    assert detail.status_code == 200
    assert set(detail.json()) == WORK_ORDER_KEYS
    assert detail.json()["status"] == "OPEN"

    updated = mobile_client.post(
        f"/api/v1/work-orders/{work_order_id}/update",
        json={"status": "IN_PROGRESS", "notes": "On site."},
        headers=headers,
    )
    assert updated.status_code == 200
    assert set(updated.json()) == WORK_ORDER_KEYS
    assert updated.json()["status"] == "IN_PROGRESS"
    assert updated.json()["notes"] == "On site."

    # Terminal move still succeeds; an illegal one is a 409.
    assert (
        mobile_client.post(
            f"/api/v1/work-orders/{work_order_id}/update",
            json={"status": "COMPLETED", "notes": "Done."},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        mobile_client.post(
            f"/api/v1/work-orders/{work_order_id}/update",
            json={"status": "IN_PROGRESS", "notes": None},
            headers=headers,
        ).status_code
        == 409
    )


def test_operator_cannot_update_work_order(mobile_client):
    operator = _login(mobile_client, ("operator", "Demo-Operator-117!"))
    headers = _auth(operator)
    technician = _login(mobile_client, TECHNICIAN)
    equipment = _first_equipment(mobile_client, _auth(technician))
    work_order_id = _create_work_order(mobile_client, equipment["id"])
    response = mobile_client.post(
        f"/api/v1/work-orders/{work_order_id}/update",
        json={"status": "IN_PROGRESS", "notes": None},
        headers=headers,
    )
    assert response.status_code == 403


# ─── Agent tasks ──────────────────────────────────────────────────────────────
def test_agent_tasks_acknowledge_and_complete(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    headers = _auth(session)

    listing = mobile_client.get("/api/v1/agents/tasks", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert items, "the fixture's engine database holds one real agent task"
    for item in items:
        assert set(item) == AGENT_TASK_KEYS
    task = items[0]
    assert task["status"] == "PENDING"

    acknowledged = mobile_client.post(
        f"/api/v1/agents/tasks/{task['id']}/acknowledge", headers=headers
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"

    completed = mobile_client.post(
        f"/api/v1/agents/tasks/{task['id']}/complete",
        json={"notes": "Checked.", "evidence_ids": ["DOC-1"]},
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"


def test_unknown_agent_task_is_404(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    response = mobile_client.post("/api/v1/agents/tasks/NOPE/acknowledge", headers=_auth(session))
    assert response.status_code == 404


# ─── Approvals ────────────────────────────────────────────────────────────────
def test_approvals_list_and_decide(mobile_client):
    technician = _login(mobile_client, TECHNICIAN)
    equipment = _first_equipment(mobile_client, _auth(technician))
    work_order_id = _create_work_order(mobile_client, equipment["id"])
    created = mobile_client.post(
        "/api/approvals",
        json={
            "title": "Shutdown approval",
            "type": "shutdown",
            "summary": "Four hour outage requested for the bearing replacement.",
            "related_id": work_order_id,
            "risk": "high",
        },
    )
    assert created.status_code == 200, created.text
    approval_id = created.json()["approval"]["id"]

    supervisor = _login(mobile_client, SUPERVISOR)
    listing = mobile_client.get("/api/v1/approvals", headers=_auth(supervisor))
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert items
    for item in items:
        assert set(item) == APPROVAL_KEYS
    assert any(item["id"] == approval_id for item in items)

    decided = mobile_client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"decision": "approve", "notes": "Authorised."},
        headers=_auth(supervisor),
    )
    assert decided.status_code == 200
    assert set(decided.json()) == APPROVAL_KEYS
    assert decided.json()["status"] == "APPROVED"

    # Deciding twice is a conflict, not a silent overwrite.
    assert (
        mobile_client.post(
            f"/api/v1/approvals/{approval_id}/decide",
            json={"decision": "reject", "notes": None},
            headers=_auth(supervisor),
        ).status_code
        == 409
    )


def test_technician_cannot_decide_approval(mobile_client):
    supervisor = _login(mobile_client, SUPERVISOR)
    technician = _login(mobile_client, TECHNICIAN)
    created = mobile_client.post(
        "/api/approvals",
        json={"title": "Second approval", "type": "shutdown", "risk": "low"},
    )
    approval_id = created.json()["approval"]["id"]
    assert (
        mobile_client.post(
            f"/api/v1/approvals/{approval_id}/decide",
            json={"decision": "approve", "notes": None},
            headers=_auth(technician),
        ).status_code
        == 403
    )
    # ...and it is still pending for the supervisor.
    rows = mobile_client.get("/api/v1/approvals", headers=_auth(supervisor)).json()["items"]
    assert all(row["status"] == "PENDING" for row in rows if row["id"] == approval_id)


# ─── Issues, notifications, evidence ──────────────────────────────────────────
def test_report_issue_notification_and_read(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    headers = _auth(session)
    equipment = _first_equipment(mobile_client, headers)

    issue = mobile_client.post(
        "/api/v1/issues",
        json={
            "equipment_id": equipment["id"],
            "description": "Abnormal vibration on the outboard bearing.",
            "severity": "CRITICAL",
            "evidence_ids": ["DOC-1"],
        },
        headers=headers,
    )
    assert issue.status_code == 201, issue.text
    assert set(issue.json()) == ISSUE_KEYS
    assert issue.json()["severity"] == "CRITICAL"
    assert issue.json()["reported_by"] == "technician"

    # Reporting the issue emitted a real notification for this user.
    notifications = mobile_client.get("/api/v1/notifications", headers=headers)
    assert notifications.status_code == 200
    items = notifications.json()["items"]
    assert items
    for item in items:
        assert set(item) == NOTIFICATION_KEYS
    assert items[0]["is_read"] is False

    marked = mobile_client.post(f"/api/v1/notifications/{items[0]['id']}/read", headers=headers)
    assert marked.status_code == 200
    reread = mobile_client.get("/api/v1/notifications", headers=headers).json()["items"]
    assert next(item for item in reread if item["id"] == items[0]["id"])["is_read"] is True


def test_report_issue_on_unknown_equipment_is_404(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    response = mobile_client.post(
        "/api/v1/issues",
        json={
            "equipment_id": "NOT-AN-ASSET",
            "description": "x",
            "severity": "LOW",
            "evidence_ids": [],
        },
        headers=_auth(session),
    )
    assert response.status_code == 404


def test_evidence_upload_returns_document_id(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    response = mobile_client.post(
        "/api/v1/documents/upload",
        files={"file": ("bearing.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"equipment_id": "e-P-1042", "work_order_id": "WO-1", "caption": "bearing"},
        headers=_auth(session),
    )
    assert response.status_code == 201, response.text
    assert set(response.json()) == {"document_id"}
    assert response.json()["document_id"]


# ─── SOP / knowledge ──────────────────────────────────────────────────────────
def test_sop_library_from_real_documents(mobile_client):
    session = _login(mobile_client)
    headers = _auth(session)

    empty = mobile_client.get("/api/v1/knowledge/sop", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"items": []}

    uploaded = mobile_client.post(
        "/api/documents/upload",
        files={
            "files": (
                "SOP_Test_Procedure.txt",
                b"Standard Operating Procedure\n\nDocument No: SOP-TEST-01\nRevision: 2\n"
                b"Effective Date: 01 Jan 2026\n\n1. Do the thing.",
                "text/plain",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["documents"][0]["id"]

    listing = mobile_client.get("/api/v1/knowledge/sop", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert set(items[0]) == SOP_KEYS

    by_id = mobile_client.get(f"/api/v1/knowledge/sop/{document_id}", headers=headers)
    assert by_id.status_code == 200
    assert set(by_id.json()) == SOP_KEYS
    assert mobile_client.get("/api/v1/knowledge/sop/NOPE", headers=headers).status_code == 404


# ─── Chat ─────────────────────────────────────────────────────────────────────
def test_chat_matches_dto(mobile_client):
    session = _login(mobile_client, TECHNICIAN)
    response = mobile_client.post(
        "/api/v1/chat",
        json={
            "message": "What is the status of the pump?",
            "equipment_id": None,
            "work_order_id": None,
        },
        headers=_auth(session),
    )
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"response"}
    assert response.json()["response"]
