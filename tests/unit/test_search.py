"""Retrieval tests (Phase 4).

Two layers:
- API/service tests use a FakeRetriever (no vendor imports, no models) to
  prove orchestration, UUID↔staged-name bridging, filter errors, citation
  extraction, auditing and chat grounding.
- An opt-in integration test exercises the real localGPT hybrid retriever
  (embed the query → LanceDB vector + FTS legs → RRF) end to end; it is
  skipped unless the vendor stack and a local Ollama are available.

The FakeRetriever returns rows in the exact shape the vendored
MultiVectorRetriever produces (document_id = staged basename, chunk_index,
text, score, metadata = JSON string of the indexed chunk dict), so the
service's bridging/citation logic is exercised against vendor reality.
"""

from __future__ import annotations

import json

import pytest
from backend.api.src.main import create_app
from backend.chat.service import ChatService
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.router import ModelRouter
from backend.rag.service import RetrievalService
from fastapi.testclient import TestClient

from tests.conftest import FakeProvider

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _vendor_row(document_id: str, chunk_index: int, text: str, page: int = 1) -> dict:
    """A row exactly as MultiVectorRetriever.retrieve() returns it."""
    chunk = {
        "chunk_id": f"{document_id}_{chunk_index}",
        "text": text,
        "metadata": {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "page": page,
            "heading_path": ["Maintenance", "Bearings"],
            "heading_level": 2,
            "block_type": "paragraph",
        },
    }
    return {
        "chunk_id": chunk["chunk_id"],
        "text": text,
        "score": 0.05 - chunk_index / 1000,
        "document_id": document_id,
        "chunk_index": chunk_index,
        "metadata": json.dumps(chunk),
    }


class FakeRetriever:
    """Deterministic stand-in for the localGPT retrieval adapter."""

    def __init__(self, rows: list[dict] | None = None, fail: bool = False) -> None:
        self.rows = rows or []
        self.fail = fail
        self.calls: list[dict] = []
        self.embedding_model = "fake-embedder"
        self.table_name = "fake_table"
        self.reranker_model = ""

    def retrieve(self, query: str, *, top_k: int, mode: str = "hybrid", where=None) -> list[dict]:
        if self.fail:
            raise RuntimeError("lancedb gone")
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "where": where})
        return self.rows[:top_k]

    def rerank(self, query: str, docs: list[dict], *, top_k: int) -> list[dict]:
        return docs[:top_k]

    def has_table(self) -> bool:
        return not self.fail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(settings: Settings, retriever: FakeRetriever) -> TestClient:
    app = create_app(settings)
    service = RetrievalService(
        retriever=retriever,  # type: ignore[arg-type]
        session_factory=app.state.session_factory,
        audit=app.state.audit,
    )
    app.state.retrieval = service
    # Chat needs a serving model in tests: install the fake provider.
    gateway = ModelGateway(providers={"fake": FakeProvider()}, default_provider="fake")
    app.state.gateway = gateway
    app.state.router = ModelRouter(gateway, ModelRoles(settings), availability_ttl=0)
    app.state.chat = ChatService(
        app.state.router,
        app.state.sessions,
        app.state.audit,
        retrieval=service,
        evidence_top_k=3,
    )
    return app


@pytest.fixture
def search_client(tmp_path):
    rows = [
        _vendor_row(
            "11111111-1111-1111-1111-111111111111.pdf",
            0,
            "Bearing inspection every 500 hours.",
            page=2,
        ),
        _vendor_row(
            "22222222-2222-2222-2222-222222222222.pdf",
            3,
            "Replace seals when wear exceeds spec.",
            page=5,
        ),
        _vendor_row(
            "11111111-1111-1111-1111-111111111111.pdf", 1, "Record vibration readings.", page=2
        ),
    ]
    retriever = FakeRetriever(rows=rows)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'search.db'}",
        uploads_dir=tmp_path / "uploads",
        reasoning_model="llama3:latest",  # served by FakeProvider
        log_level="WARNING",
    )
    app = make_app(settings, retriever)
    with TestClient(app) as client:
        yield client, retriever


def _upload(client: TestClient, name: str = "manual.pdf") -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"files": (name, b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["documents"][0]


# ---------------------------------------------------------------------------
# API tests (fake pipeline)
# ---------------------------------------------------------------------------


def test_search_returns_citations(search_client):
    client, _ = search_client
    response = client.post("/api/search", json={"query": "bearing inspection", "top_k": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["mode"] == "hybrid"
    first = body["results"][0]
    assert first["text"].startswith("Bearing inspection")
    citation = first["citation"]
    assert citation["document_id"] == "11111111-1111-1111-1111-111111111111"
    assert citation["page"] == 2
    assert citation["heading_path"] == ["Maintenance", "Bearings"]
    assert citation["block_type"] == "paragraph"
    assert citation["chunk_index"] == 0


def test_search_is_audited(search_client):
    client, _ = search_client
    client.post("/api/search", json={"query": "vibration"})
    events = client.get("/api/audit", params={"action": "search.performed"}).json()
    assert events["total"] == 1
    detail = events["events"][0]["detail"]
    assert detail["mode"] == "hybrid"
    assert detail["results"] == 3
    assert "bearing" not in json.dumps(detail).lower()  # never the query text


def test_search_scopes_to_indexed_documents(tmp_path):
    """document_ids are UUIDs; the service translates them to staged names."""
    rows = [_vendor_row("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.pdf", 0, "target chunk")]
    retriever = FakeRetriever(rows=rows)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'scope.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    app = make_app(settings, retriever)
    with TestClient(app) as client:
        document = _upload(client)
        # Mark it indexed with the ingestion metadata the real pipeline writes.
        import json as _json

        from backend.database.models import Document

        with app.state.session_factory() as session:
            row = session.get(Document, document["id"])
            row.status = "indexed"
            row.metadata_json = _json.dumps(
                {
                    "ingestion": {
                        "indexed": True,
                        "chunk_count": 1,
                        "index_document_id": f"{document['id']}.pdf",
                    }
                }
            )
            session.commit()

        response = client.post(
            "/api/search", json={"query": "target", "document_ids": [document["id"]]}
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        # The where-clause must target the staged basename, not the UUID.
        assert retriever.calls[-1]["where"] == (f"document_id IN ('{document['id']}.pdf')")


def test_search_unknown_document_is_404_class(search_client):
    client, _ = search_client
    response = client.post(
        "/api/search", json={"query": "x", "document_ids": ["00000000-0000-0000-0000-000000000000"]}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "index_unavailable"


def test_search_document_not_indexed_is_409(search_client):
    client, _ = search_client
    document = _upload(client)  # stored but never reindexed
    response = client.post("/api/search", json={"query": "x", "document_ids": [document["id"]]})
    assert response.status_code == 409
    assert "not indexed" in response.json()["error"]["message"]


def test_search_invalid_filter_is_400_class(search_client):
    client, _ = search_client
    response = client.post("/api/search", json={"query": "x", "filters": {"page": {"gte": 1}}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "retrieval_failed"
    assert "invalid filters" in response.json()["error"]["message"]


def test_search_vendor_failure_maps_to_typed_error(tmp_path):
    retriever = FakeRetriever(fail=True)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'fail.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    app = make_app(settings, retriever)
    with TestClient(app) as client:
        response = client.post("/api/search", json={"query": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "retrieval_failed"


def test_search_empty_result_is_200(search_client):
    client, retriever = search_client
    retriever.rows = []
    response = client.post("/api/search", json={"query": "nothing matches"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["results"] == []


def test_search_validation_errors(search_client):
    client, _ = search_client
    assert client.post("/api/search", json={"query": ""}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "mode": "bogus"}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "top_k": 0}).status_code == 422


# ---------------------------------------------------------------------------
# Chat grounding tests
# ---------------------------------------------------------------------------


def test_chat_use_rag_returns_evidence_and_grounded_prompt(search_client):
    client, retriever = search_client
    response = client.post(
        "/api/chat", json={"message": "how often do we inspect bearings?", "use_rag": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["evidence"]) == 3  # evidence_top_k=3
    # The fake provider echoes the last message; the system prompt carried the
    # evidence snippets, so the message count includes it (system + user).
    assert body["response"].startswith("n=2:")


def test_chat_without_use_rag_has_no_evidence(chat_client):
    response = chat_client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["evidence"] == []


def test_chat_grounded_failure_degrades_gracefully(tmp_path):
    """Retrieval down + use_rag=True → the turn still answers, ungrounded."""
    retriever = FakeRetriever(
        rows=[_vendor_row("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.pdf", 0, "chunk")]
    )
    retriever.fail = True  # retrieve() raises; has_table() also False

    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'degrade.db'}",
        uploads_dir=tmp_path / "uploads",
        reasoning_model="llama3:latest",
        log_level="WARNING",
    )
    app = make_app(settings, retriever)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat", json={"message": "q", "use_rag": True, "model": "llama3:latest"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == []
    assert body["response"].startswith("n=2:")  # system + user, no evidence block


def test_chat_stream_emits_evidence_event(search_client):
    client, _ = search_client
    events: list[dict] = []
    with client.stream(
        "POST", "/api/chat/stream", json={"message": "seals", "use_rag": True}
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("data:") and line != "data: [DONE]":
                events.append(json.loads(line[5:]))
    types = [e["type"] for e in events]
    assert "evidence" in types
    start = next(e for e in events if e["type"] == "start")
    assert start["grounded"] is True
    evidence_event = next(e for e in events if e["type"] == "evidence")
    assert evidence_event["evidence"][0]["citation"]["page"] == 2


def test_chat_response_matches_the_declared_contract(search_client):
    """The declared response model must describe what the route returns.

    ``schemas/chat.py`` previously declared a ``ChatResponse`` with fields the
    route never returned, and nothing compared the two — the class was exported,
    documented a contract, and was wrong. Asserting the declared model against a
    live payload is what makes that class load-bearing instead of decorative.
    """
    from backend.api.src.schemas.chat import ChatResponse

    client, _ = search_client
    body = client.post(
        "/api/chat", json={"message": "how often do we inspect bearings?", "use_rag": True}
    ).json()

    declared = set(ChatResponse.model_fields)
    assert declared == set(body), (
        f"declared {sorted(declared)} but the route returned {sorted(body)}"
    )
    # And the payload must actually validate against the declaration.
    parsed = ChatResponse.model_validate(body)
    assert parsed.evidence, "grounded turn must carry evidence"
    assert parsed.evidence[0].citation.document_id


# ---------------------------------------------------------------------------
# Opt-in integration test: real vendor retriever + real Ollama
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
def test_real_hybrid_search(tmp_path):
    """Index a real PDF, then retrieve it through the localGPT hybrid leg.

    Opt-in (uv run pytest -m integration): requires docling/lancedb and
    Ollama serving the configured embedder locally.
    """
    pytest.importorskip("docling")
    pytest.importorskip("lancedb")
    pytest.importorskip("fitz")
    embedding_model = "nomic-embed-text:latest"
    if not _ollama_reachable(embedding_model):
        pytest.skip(f"Ollama does not serve {embedding_model} at localhost:11434")

    # Build + ingest a real PDF through the Phase 3 pipeline.
    import fitz

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for page_index in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Compressor Maintenance Manual — part {page_index + 1}")
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
    app = create_app(settings)
    with TestClient(app) as client:
        upload = client.post(
            "/api/documents/upload",
            files={"files": ("sample.pdf", pdf_path.read_bytes(), "application/pdf")},
        )
        document_id = upload.json()["documents"][0]["id"]
        reindex = client.post(f"/api/documents/{document_id}/reindex")
        assert reindex.status_code == 200, reindex.text

        search = client.post("/api/search", json={"query": "bearing inspection hours", "top_k": 3})
        assert search.status_code == 200, search.text
        body = search.json()
        assert body["total"] > 0
        top = body["results"][0]
        assert top["citation"]["document_id"] == document_id
        assert top["citation"]["page"] is not None
        assert "bearing" in top["text"].lower()

        scoped = client.post(
            "/api/search", json={"query": "bearing inspection", "document_ids": [document_id]}
        )
        assert scoped.status_code == 200
        assert scoped.json()["total"] > 0
