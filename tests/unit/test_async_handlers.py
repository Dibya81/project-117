"""Tests for Phase 2 fix: async/sync handler consistency in routes.

The core assertion: upload_documents and any other route that delegates to
blocking storage/disk I/O must NOT be declared ``async def``. FastAPI
offloads plain ``def`` handlers to a threadpool automatically; an ``async def``
handler that calls blocking code runs it on the event loop, stalling all
other requests.
"""

from __future__ import annotations

import inspect


class TestUploadDocumentsIsNotAsync:
    """upload_documents must be a plain def, not async def."""

    def test_upload_documents_is_plain_def(self):
        from backend.api.src.routes.documents import upload_documents

        assert not inspect.iscoroutinefunction(upload_documents), (
            "upload_documents is declared async def but calls blocking save_upload "
            "directly. Change it to plain def so FastAPI offloads it to a "
            "threadpool worker (matching list_documents, get_document, delete_document "
            "in the same file)."
        )

    def test_sibling_handlers_are_also_plain_def(self):
        """Regression guard: the sibling handlers that were already correct stay correct."""
        from backend.api.src.routes.documents import (
            delete_document,
            get_document,
            list_documents,
        )

        for fn in (list_documents, get_document, delete_document):
            assert not inspect.iscoroutinefunction(fn), (
                f"{fn.__name__} must remain a plain def handler"
            )

    def test_reindex_document_stays_async(self):
        """reindex_document correctly uses run_in_executor and must stay async def."""
        from backend.api.src.routes.documents import reindex_document

        assert inspect.iscoroutinefunction(reindex_document), (
            "reindex_document uses asyncio.get_running_loop().run_in_executor and "
            "must stay async def."
        )


class TestMobileUploadEvidenceIsNotAsync:
    """upload_evidence in mobile/field.py has the same pattern — must be plain def."""

    def test_upload_evidence_is_plain_def(self):
        from backend.api.src.routes.mobile.field import upload_evidence

        assert not inspect.iscoroutinefunction(upload_evidence), (
            "upload_evidence is declared async def but calls blocking save_upload "
            "and record_evidence_upload directly. Change it to plain def."
        )


class TestUploadRoundtripStillWorks:
    """Integration smoke test: the upload still works after the signature change."""

    def test_upload_list_roundtrip(self, client):
        response = client.post(
            "/api/documents/upload",
            files={"files": ("phase2.txt", b"phase 2 test content", "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["uploaded"] == 1
        assert data["documents"][0]["filename"] == "phase2.txt"
