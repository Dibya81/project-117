"""Regression tests for two error-reporting defects found by running real calls.

Both were "wrong answer, no exception" bugs: the code ran, returned a
plausible-looking result, and was simply wrong.

* ``ToolError`` derives from ``RuntimeError``. No handler matched it, so bad
  arguments, an unknown tool, and a tool awaiting human approval all returned
  HTTP 500 — a client mistake reported as a server crash.
* LanceDB 0.38 returns a ``ListTablesResponse`` from ``list_tables()``, not a
  list of names. ``name not in db.list_tables()`` was therefore always false,
  so a table that existed and held rows was reported as empty. That made
  ``chunk_count`` return 0 for a document that had just been indexed, made
  deletes report zero rows purged, and made retrieval claim the corpus was
  empty after a clean ingest.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from backend.storage.lancedb import has_table, table_names
from backend.tools.base import ToolArgumentError, ToolNotFound


class _ListTablesResponse(NamedTuple):
    """Stand-in for lancedb's paginated response object.

    It is a named tuple, exactly like the real one, which is the whole reason
    the old membership test failed quietly: ``"t" in response`` iterates the
    *field values* (``context``, ``tables``, ``page_token``) rather than the
    table names, so it answers False for a table that is present.
    """

    context: Any = None
    tables: list[str] = []
    page_token: Any = None


class _ModernDB:
    def __init__(self, tables: list[str]) -> None:
        self._tables = tables

    def list_tables(self):
        return _ListTablesResponse(tables=self._tables)


class _LegacyDB:
    """Pre-0.38 shape: ``list_tables()`` returned a plain list."""

    def __init__(self, tables: list[str]) -> None:
        self._tables = tables

    def list_tables(self):
        return list(self._tables)


def test_table_names_reads_paginated_response():
    db = _ModernDB(["p117_chunks", "other"])
    assert table_names(db) == {"p117_chunks", "other"}
    assert has_table(db, "p117_chunks") is True


def test_table_names_handles_legacy_list_shape():
    assert table_names(_LegacyDB(["a"])) == {"a"}


def test_has_table_is_false_when_absent():
    assert has_table(_ModernDB(["other"]), "p117_chunks") is False


def test_membership_against_response_object_would_be_wrong():
    """Documents the trap the helper exists to avoid.

    This is the assertion the old code effectively made. If a future refactor
    reaches for ``db.list_tables()`` directly again, this shows why it fails.
    """
    response = _ListTablesResponse(["p117_chunks"])
    assert ("p117_chunks" in response) is False
    assert has_table(_ModernDB(["p117_chunks"]), "p117_chunks") is True


# --- tool error status mapping --------------------------------------------


def test_unknown_tool_is_404(client):
    response = client.post("/api/tools/execute", json={"tool": "no-such-tool", "arguments": {}})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tool_not_found"


def test_bad_tool_arguments_are_400_not_500(client):
    response = client.post("/api/tools/execute", json={"tool": "run_python", "arguments": {}})
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "tool_invalid_arguments"


def test_execute_risk_tool_reports_409_approval_required(client):
    """A manual call can never carry prior approval, so it must ask, not crash."""
    response = client.post(
        "/api/tools/execute",
        json={"tool": "run_python", "arguments": {"code": "print(1)"}},
    )
    assert response.status_code == 409, response.text
    body = response.json()["error"]
    assert body["code"] == "approval_required"
    # The caller needs these to route the request into the approval flow.
    assert body["tool"] == "run_python"
    assert body["risk"]


def test_tool_errors_are_the_expected_types():
    assert issubclass(ToolNotFound, RuntimeError)
    assert issubclass(ToolArgumentError, RuntimeError)
