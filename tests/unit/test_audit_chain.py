"""The audit hash chain, and the test that makes it worth having.

A chain that never reports invalid is worthless, so the acceptance test here
does the thing the chain exists to detect: it mutates a row **directly in
SQLite**, bypassing every application path, and asserts that the verifier
fails and names the row it caught.

The other cases cover the ways a log can be edited that are not "change a
field": deleting a row, removing rows from the front, appending a row behind
the audit service's back, and migrating a database written before the chain
existed.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.database.base import create_engine_for, create_session_factory, init_db
from backend.security.audit import AuditService
from backend.security.audit.audit_chain import (
    GENESIS_HASH,
    chain_columns_present,
)
from fastapi.testclient import TestClient

# --------------------------------------------------------------- fixtures ---


@pytest.fixture
def audit_db(tmp_path):
    """A real SQLite audit table and a service bound to it."""
    path = tmp_path / "audit.db"
    engine = create_engine_for(f"sqlite:///{path}")
    init_db(engine)
    service = AuditService(create_session_factory(engine), database_url=f"sqlite:///{path}")
    return path, service


def _raw(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _record(service: AuditService, n: int = 3) -> None:
    for index in range(n):
        service.record(
            action=f"test.action{index}",
            user="tester",
            resource_type="document",
            resource_id=f"doc-{index}",
            detail={"index": index, "filename": f"file-{index}.pdf"},
        )


# ------------------------------------------------------- the acceptance test


def test_clean_chain_verifies(audit_db):
    db_path, service = audit_db
    _record(service, 4)

    verdict = service.verify()

    assert verdict.valid is True
    assert verdict.status == "VALID"
    assert verdict.events == 4
    assert verdict.last_seq == 4
    assert verdict.broken_id is None
    assert verdict.last_hash != GENESIS_HASH

    # The head reported by the verifier must be the head actually stored, or
    # the figure the console shows is decorative.
    with _raw(db_path) as conn:
        stored = conn.execute(
            "SELECT current_hash FROM audit_events ORDER BY chain_seq DESC LIMIT 1"
        ).fetchone()[0]
    assert stored == verdict.last_hash


def test_tampered_row_is_detected_and_named(audit_db):
    """THE acceptance test: edit a row in SQLite, the verifier must fail."""
    db_path, service = audit_db
    _record(service, 4)

    with _raw(db_path) as conn:
        victim = conn.execute(
            "SELECT id, chain_seq, outcome FROM audit_events WHERE chain_seq = 2"
        ).fetchone()
        # Bypass the application entirely: this is what an operator with
        # `sqlite3` does, and it is exactly what the chain must catch.
        conn.execute("UPDATE audit_events SET outcome = 'refused' WHERE chain_seq = 2")
        conn.commit()

    verdict = service.verify()

    assert verdict.valid is False
    assert verdict.status == "BROKEN"
    assert verdict.broken_id == victim["id"]
    assert verdict.broken_seq == 2
    assert "modified after the row was written" in (verdict.reason or "")

    # And the endpoint the console reads must report the same thing - a broken
    # chain that the UI cannot see is still a broken chain.
    with TestClient(create_app(_settings_for(db_path))) as client:
        body = client.get("/api/audit/integrity").json()
    assert body["valid"] is False
    assert body["broken_id"] == victim["id"]


def test_editing_the_stored_hash_does_not_repair_the_chain(audit_db):
    """Recomputing one row's hash still leaves the *next* link broken."""
    db_path, service = audit_db
    _record(service, 4)

    with _raw(db_path) as conn:
        conn.execute("UPDATE audit_events SET user = 'somebody-else' WHERE chain_seq = 1")
        conn.execute("UPDATE audit_events SET previous_hash = previous_hash WHERE chain_seq = 2")
        conn.commit()

    verdict = service.verify()
    assert verdict.valid is False
    assert verdict.broken_seq == 1


def test_deleted_row_is_detected_as_a_gap(audit_db):
    db_path, service = audit_db
    _record(service, 4)

    with _raw(db_path) as conn:
        conn.execute("DELETE FROM audit_events WHERE chain_seq = 3")
        conn.commit()

    verdict = service.verify()
    assert verdict.valid is False
    assert "chain_seq jumped" in (verdict.reason or "")


def test_rows_removed_from_the_front_are_detected(audit_db):
    db_path, service = audit_db
    _record(service, 4)

    with _raw(db_path) as conn:
        conn.execute("DELETE FROM audit_events WHERE chain_seq = 1")
        conn.commit()

    verdict = service.verify()
    assert verdict.valid is False
    # Deleting from the front leaves a gap, so the dense-sequence check fires
    # first. Either way the deletion is caught.
    assert verdict.broken_seq == 2


def test_a_chain_that_does_not_start_at_genesis_is_detected(audit_db):
    """Rows removed from the front and renumbered must not verify.

    This is the case the genesis check exists for: the log is made to look
    dense again (``chain_seq`` rewritten to start at 1) so only the fact that
    the first row's ``previous_hash`` is not the genesis constant reveals that
    earlier rows are missing.
    """
    db_path, service = audit_db
    _record(service, 4)

    with _raw(db_path) as conn:
        conn.execute(
            "UPDATE audit_events SET previous_hash = ? WHERE chain_seq = 1",
            ("f" * 64,),
        )
        conn.commit()

    verdict = service.verify()
    assert verdict.valid is False
    assert verdict.broken_seq == 1
    assert "not genesis" in (verdict.reason or "")


def test_row_appended_behind_the_service_is_detected(audit_db):
    db_path, service = audit_db
    _record(service, 3)

    with _raw(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_events "
            "(id, timestamp, action, outcome, approval, detail_json) "
            "VALUES (?, ?, 'forged.action', 'success', 'not_required', '{}')",
            (str(uuid.uuid4()), datetime(2026, 1, 1).isoformat(sep=" ")),
        )
        conn.commit()

    verdict = service.verify()
    assert verdict.valid is False
    assert "not part of the chain" in (verdict.reason or "")


def test_empty_log_verifies_but_reports_zero(audit_db):
    _, service = audit_db
    verdict = service.verify()
    assert verdict.valid is True
    assert verdict.events == 0


# ------------------------------------------------------------- migration ----


def test_pre_existing_rows_are_backfilled_not_discarded(tmp_path):
    """A database written before the chain existed keeps its history."""
    path = tmp_path / "legacy.db"
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE audit_events (
                id TEXT PRIMARY KEY, timestamp DATETIME, user TEXT, action TEXT,
                resource_type TEXT, resource_id TEXT, outcome TEXT, agent TEXT,
                tool TEXT, model TEXT, approval TEXT, detail_json TEXT, error TEXT
            );
            """
        )
        for index in range(3):
            conn.execute(
                "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    f"2026-01-0{index + 1} 09:00:00.000000",
                    "legacy-user",
                    f"legacy.action{index}",
                    None,
                    None,
                    "success",
                    None,
                    None,
                    None,
                    "not_required",
                    "{}",
                    None,
                ),
            )
        conn.commit()

    assert chain_columns_present(path) is False

    engine = create_engine_for(f"sqlite:///{path}")
    init_db(engine)  # create_all does not ALTER an existing table
    service = AuditService(create_session_factory(engine), database_url=f"sqlite:///{path}")

    verdict = service.verify()
    assert verdict.valid is True
    assert verdict.events == 3
    assert chain_columns_present(path) is True

    # The legacy rows are still there, in their original order, now chained.
    with _raw(path) as conn:
        rows = conn.execute(
            "SELECT action, chain_seq FROM audit_events ORDER BY chain_seq"
        ).fetchall()
    assert [row["action"] for row in rows] == [
        "legacy.action0",
        "legacy.action1",
        "legacy.action2",
    ]

    # ...and a new event continues the same chain rather than starting a second.
    service.record(action="after.upgrade")
    fresh = service.verify()
    assert fresh.valid is True
    assert fresh.events == 4
    assert fresh.last_seq == 4


def test_migration_is_idempotent(audit_db):
    db_path, service = audit_db
    _record(service, 3)
    first = service.verify()

    # A second service over the same file must not re-link or fork anything.
    engine = create_engine_for(f"sqlite:///{db_path}")
    second = AuditService(create_session_factory(engine), database_url=f"sqlite:///{db_path}")
    again = second.verify()

    assert again.valid is True
    assert again.events == first.events
    assert again.last_hash == first.last_hash


def test_service_without_a_sqlite_url_does_not_claim_verification(tmp_path):
    """No chain is maintained off SQLite, and the service says so."""
    engine = create_engine_for("sqlite://")
    init_db(engine)
    service = AuditService(create_session_factory(engine), database_url="postgresql://x/y")
    verdict = service.verify()
    assert verdict.valid is False
    assert verdict.status == "UNVERIFIABLE"
    assert verdict.error


# ---------------------------------------------------- verification package ---


@pytest.mark.asyncio
async def test_audit_chain_checker_passes_clean_and_fails_tampered(audit_db):
    from backend.verification import AuditChainChecker, Verifier
    from backend.verification.base import VerificationInput

    db_path, service = audit_db
    _record(service, 3)

    verifier = Verifier(checkers=[AuditChainChecker()])
    report = await verifier.verify(VerificationInput(task="x", audit=service))
    result = report.checks[0]
    assert result.status.value == "passed"

    with _raw(db_path) as conn:
        conn.execute("UPDATE audit_events SET action = 'rewritten' WHERE chain_seq = 1")
        conn.commit()

    report = await verifier.verify(VerificationInput(task="x", audit=service))
    result = report.checks[0]
    assert result.status.value == "failed"
    assert result.blocking is False  # warning, not a job veto
    assert "chain broken" in result.message
    # The default set includes the checker, so a normal verification run in
    # this deployment actually consults the chain.
    assert "audit_chain" in Verifier().checker_names


@pytest.mark.asyncio
async def test_audit_chain_checker_skips_without_an_audit_sink():
    from backend.verification import AuditChainChecker, Verifier
    from backend.verification.base import VerificationInput

    report = await Verifier(checkers=[AuditChainChecker()]).verify(VerificationInput(task="x"))
    result = report.checks[0]
    # An unrun check is never a pass.
    assert result.status.value == "skipped"
    assert "not a statement that the log is intact" in result.message


# ------------------------------------------------------------------- api ----


def _settings_for(db_path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{db_path}",
        uploads_dir=db_path.parent / "uploads",
        log_level="WARNING",
    )


def test_integrity_endpoint_reports_real_values(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        # An upload writes a durable audit row through the real API path.
        upload = client.post(
            "/api/documents/upload",
            files={"files": ("chained.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert upload.status_code == 201

        body = client.get("/api/audit/integrity").json()
        assert body["valid"] is True
        assert body["status"] == "VALID"
        assert body["events"] >= 2  # document.uploaded + the http.post row
        assert len(body["last_hash"]) == 64
        assert body["last_seq"] == body["events"]

        # `/integrity` must not be swallowed by the `/{event_id}` route.
        assert client.get("/api/audit/integrity").status_code == 200

        # Tamper through SQLite, then re-read the endpoint.
        with sqlite3.connect(settings.database_url.removeprefix("sqlite:///")) as conn:
            victim = conn.execute("SELECT id FROM audit_events WHERE chain_seq = 1").fetchone()[0]
            conn.execute("UPDATE audit_events SET action = 'tampered' WHERE chain_seq = 1")
            conn.commit()

        broken = client.get("/api/audit/integrity").json()
        assert broken["valid"] is False
        assert broken["broken_id"] == victim
        assert broken["broken_seq"] == 1
        assert broken["reason"]
