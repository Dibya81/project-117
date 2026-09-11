"""Ingestion tests.

Two layers:
- API/service tests use a FakeIndexer (no vendor imports, no models) to prove
  orchestration, status transitions, audit and error mapping.
- An opt-in integration test exercises the real localGPT pipeline
  (docling → chunk → Ollama embeddings → LanceDB) end to end; it is skipped
  unless the vendor stack and a local Ollama are available.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.ingestion import DocumentStager, IngestionService, LocalGPTIndexer
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeIndexer:
    """Deterministic stand-in for the localGPT adapter. No vendor imports."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.indexed: list[Path] = []
        self.deleted: list[str] = []
        self.embedding_model = "fake-embedder"
        self.table_name = "fake_table"

    def index_file(self, staged_path: Path) -> dict:
        if self.fail:
            raise RuntimeError("conversion failed")
        self.indexed.append(staged_path)
        return {
            "staged_path": str(staged_path),
            "document_id": staged_path.stem,
            "elapsed_seconds": 0.01,
        }

    def delete_document(self, document_id: str) -> int:
        self.deleted.append(document_id)
        return 3

    def chunk_count(self, document_id: str | None = None) -> int:
        return 3 if not self.fail else 0


def make_app(settings: Settings, indexer: FakeIndexer):
    app = create_app(settings)
    ingestion = IngestionService(
        session_factory=app.state.session_factory,
        stager=DocumentStager(settings.uploads_dir / "staging"),
        indexer=indexer,  # type: ignore[arg-type]
        audit=app.state.audit,
        ingestible_extensions=settings.ingestible_extensions,
        uploads_dir=settings.uploads_dir,
    )
    app.state.ingestion = ingestion
    return app


# ---------------------------------------------------------------------------
# API tests (fake pipeline)
# ---------------------------------------------------------------------------


@pytest.fixture
def ingest_client(tmp_path):
    indexer = FakeIndexer()
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'ingest.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    app = make_app(settings, indexer)
    with TestClient(app) as client:
        yield client, indexer


def _upload(client: TestClient, name: str = "manual.pdf", body: bytes = b"%PDF-1.4 fake") -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"files": (name, body, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["documents"][0]


def test_reindex_success_flow(ingest_client):
    client, indexer = ingest_client
    document = _upload(client)
    response = client.post(f"/api/documents/{document['id']}/reindex")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "indexed"
    assert body["chunk_count"] == 3
    assert body["document_id"] == document["id"]

    # Document row reflects the new state + ingestion metadata.
    got = client.get(f"/api/documents/{document['id']}").json()
    assert got["status"] == "indexed"
    ingestion_meta = got["metadata"]["ingestion"]
    assert ingestion_meta["indexed"] is True
    assert ingestion_meta["chunk_count"] == 3
    assert ingestion_meta["last_index_error"] is None

    # The stager handed the pipeline a UUID-named symlink.
    assert len(indexer.indexed) == 1
    staged = indexer.indexed[0]
    assert staged.stem == document["id"]
    assert staged.is_symlink(), "staging must use symlinks, not copies"


def test_reindex_failure_marks_document_failed(ingest_client):
    client, indexer = ingest_client
    indexer.fail = True
    document = _upload(client)
    response = client.post(f"/api/documents/{document['id']}/reindex")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "ingestion_failed"

    got = client.get(f"/api/documents/{document['id']}").json()
    assert got["status"] == "failed"
    assert got["metadata"]["ingestion"]["indexed"] is False
    assert "conversion failed" in got["metadata"]["ingestion"]["last_index_error"]

    # The failure is auditable.
    audit = client.get(
        "/api/audit", params={"resource_type": "document", "resource_id": document["id"]}
    ).json()
    actions = [event["action"] for event in audit["events"]]
    assert "document.index_failed" in actions


def test_reindex_missing_document_404(ingest_client):
    client, _ = ingest_client
    assert client.post("/api/documents/nope/reindex").status_code == 404


def test_reindex_unsupported_extension(ingest_client):
    client, _ = ingest_client
    response = client.post(
        "/api/documents/upload",
        files={"files": ("scan.png", b"\x89PNG", "image/png")},
    )
    assert response.status_code == 201
    document = response.json()["documents"][0]
    response = client.post(f"/api/documents/{document['id']}/reindex")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_for_ingestion"


def test_reindex_is_idempotent_replacing_previous_vectors(ingest_client):
    client, indexer = ingest_client
    document = _upload(client)
    client.post(f"/api/documents/{document['id']}/reindex")
    client.post(f"/api/documents/{document['id']}/reindex")
    assert len(indexer.indexed) == 2  # re-staged and re-run


def test_delete_purges_vectors(ingest_client):
    client, indexer = ingest_client
    document = _upload(client)
    client.post(f"/api/documents/{document['id']}/reindex")
    deleted = client.delete(f"/api/documents/{document['id']}")
    assert deleted.status_code == 200
    # Purge targets the staged basename (uuid + ext) and the bare id fallback.
    assert f"{document['id']}.pdf" in indexer.deleted
    assert document["id"] in indexer.deleted

    audit = client.get(
        "/api/audit", params={"resource_type": "document", "resource_id": document["id"]}
    ).json()
    actions = [event["action"] for event in audit["events"]]
    assert "document.index_purged" in actions


def test_delete_works_even_if_purge_fails(tmp_path):
    class BrokenIndexer(FakeIndexer):
        def delete_document(self, document_id: str) -> int:
            raise RuntimeError("lancedb gone")

    indexer = BrokenIndexer()
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'broken.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    app = make_app(settings, indexer)
    with TestClient(app) as client:
        document = _upload(client)
        response = client.delete(f"/api/documents/{document['id']}")
        assert response.status_code == 200, "delete must not be blocked by purge failure"


# ---------------------------------------------------------------------------
# Unit tests: staging + config parsing
# ---------------------------------------------------------------------------


def test_stager_creates_uuid_named_symlink(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "stored-file.pdf").write_bytes(b"%PDF-1.4")
    stager = DocumentStager(tmp_path / "staging")

    link = stager.stage("doc-123", uploads, "stored-file.pdf")
    assert link.name == "doc-123.pdf"
    assert link.is_symlink()
    assert link.resolve() == (uploads / "stored-file.pdf").resolve()
    assert stager.basename("doc-123", ".pdf") == "doc-123.pdf"

    stager.unstage("doc-123")
    assert not link.exists()


def test_stager_missing_source_raises(tmp_path):
    stager = DocumentStager(tmp_path / "staging")
    with pytest.raises(RuntimeError, match="missing"):
        stager.stage("ghost", tmp_path, "not-there.pdf")


def test_ingestible_extensions_env_parsing(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'x.db'}",
        uploads_dir=tmp_path / "up",
        ingestible_extensions=".PDF , .docx",
        log_level="WARNING",
    )
    assert settings.ingestible_extensions == {".pdf", ".docx"}


# ---------------------------------------------------------------------------
# Opt-in integration test: real vendor pipeline + real Ollama
# ---------------------------------------------------------------------------


def _ollama_reachable(model: str) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as response:
            models = {m["name"] for m in json.load(response).get("models", [])}
        return model in models
    except Exception:
        return False


@pytest.mark.integration
def test_real_ingestion_pipeline(tmp_path):
    """Full localGPT pipeline against a real PDF and the local Ollama.

    Opt-in (uv run pytest -m integration): requires the vendored localGPT
    dependencies and Ollama serving the configured embedder locally.
    """
    pytest.importorskip("docling")
    pytest.importorskip("lancedb")
    embedding_model = "nomic-embed-text:latest"
    if not _ollama_reachable(embedding_model):
        pytest.skip(f"Ollama does not serve {embedding_model} at localhost:11434")

    # Minimal real PDF with a text layer (PyMuPDF writes one).
    import fitz

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for page_index in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Compressor Maintenance Manual — section {page_index + 1}")
        page.insert_text(
            (72, 120),
            f"Bearing inspection must occur every {500 + page_index * 250} operating hours. "
            "Record vibration readings and replace seals if wear exceeds specification.",
        )
    doc.save(pdf_path)
    doc.close()

    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'integration.db'}",
        uploads_dir=tmp_path / "uploads",
        lancedb_dir=tmp_path / "lancedb",
        lancedb_table="integration_chunks",
        embedding_model=embedding_model,
        chunk_size_tokens=128,
        log_level="WARNING",
    )
    app = make_app(settings, LocalGPTIndexer(
        db_path=settings.lancedb_dir,
        table_name=settings.lancedb_table,
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_sentences,
        embedding_model=embedding_model,
        ollama_host="http://localhost:11434",
    ))
    with TestClient(app) as client:
        upload = client.post(
            "/api/documents/upload",
            files={"files": ("sample.pdf", pdf_path.read_bytes(), "application/pdf")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["documents"][0]["id"]

        reindex = client.post(f"/api/documents/{document_id}/reindex")
        assert reindex.status_code == 200, reindex.text
        assert reindex.json()["status"] == "indexed"
        assert reindex.json()["chunk_count"] > 0

        got = client.get(f"/api/documents/{document_id}").json()
        assert got["status"] == "indexed"
