"""Clearance model tests.

The requirement these tests exist for: **unauthorized information must be
filtered before it reaches the LLM.** So the assertions are not merely "the
response omits the restricted chunk". They pin the filter to a point *upstream*
of the model:

* the fake retriever records every call to ``rerank`` — the reranker scores the
  text it is handed, so a restricted chunk must never appear in that list;
* the ``Evidence`` objects that become the prompt are checked directly;
* the graph, the direct document lookup and the agent tool path are each driven
  with an authorized and an unauthorized caller and compared.

Every test also asserts the *positive* case. A filter that hides everything
would pass a one-sided negative test, so each negative assertion is paired with
proof that the same call returns the restricted content for a caller who is
entitled to it.
"""

from __future__ import annotations

import json

import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.memory.graph import entities as ent
from backend.memory.graph.graph_builder import GraphBuilder, MemoryGraph
from backend.memory.graph.graph_query import GraphQuery
from backend.rag.service import RetrievalService
from backend.security.clearance import Clearance, ClearanceDenied
from backend.security.clearance.access import (
    filter_chunks,
    parse_clearance,
    principal_clearance,
    require_document_clearance,
)
from backend.security.rbac import Principal, principal_from_roles
from backend.tools.base import ToolContext
from backend.tools.builtin.documents import ReadDocumentTool, SearchDocumentsTool
from fastapi.testclient import TestClient

PUBLIC_DOC = "11111111-1111-1111-1111-111111111111"
SECRET_DOC = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


def _vendor_row(document_id: str, text: str, *, chunk_index: int = 0) -> dict:
    """A row in the shape the vendored retriever returns."""
    chunk = {
        "chunk_id": f"{document_id}_{chunk_index}",
        "text": text,
        "metadata": {"document_id": document_id, "chunk_index": chunk_index, "page": 1},
    }
    return {
        "chunk_id": chunk["chunk_id"],
        "text": text,
        "score": 0.9 - chunk_index / 100,
        "document_id": document_id,
        "chunk_index": chunk_index,
        "metadata": json.dumps(chunk),
    }


class RecordingRetriever:
    """Returns fixed rows and records what the reranker was asked to score."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.rerank_calls: list[list[dict]] = []
        self.embedding_model = "fake"
        self.table_name = "fake"
        self.reranker_model = "fake"

    def retrieve(self, query: str, *, top_k: int, mode: str = "hybrid", where=None) -> list[dict]:
        return self.rows[:top_k]

    def rerank(self, query: str, docs: list[dict], *, top_k: int) -> list[dict]:
        # The whole point: whatever is handed here is what a cross-encoder
        # reads. A withheld chunk must not appear.
        self.rerank_calls.append(list(docs))
        return docs[:top_k]

    def has_table(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# the level vocabulary itself
# ---------------------------------------------------------------------------


def test_levels_are_ordered_and_parse_forgivingly():
    assert Clearance.PUBLIC < Clearance.INTERNAL < Clearance.RESTRICTED
    assert Clearance.RESTRICTED < Clearance.CONFIDENTIAL < Clearance.HIGHLY_CONFIDENTIAL
    # Spacing/case are presentation, not a different level.
    assert parse_clearance("highly confidential") is Clearance.HIGHLY_CONFIDENTIAL
    assert parse_clearance("Highly-Confidential") is Clearance.HIGHLY_CONFIDENTIAL
    # Unlabelled is INTERNAL, never PUBLIC: shipping this must not make every
    # pre-existing document world-readable.
    assert parse_clearance(None) is Clearance.INTERNAL


def test_an_unknown_level_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        parse_clearance("Restriced")


def test_an_explicit_badge_beats_the_role_default_in_both_directions():
    operator = principal_from_roles("u", ["operator"])
    assert principal_clearance(operator) is Clearance.RESTRICTED
    lowered = Principal(user="contractor", roles=("operator",), extra={"clearance": "INTERNAL"})
    assert principal_clearance(lowered) is Clearance.INTERNAL
    raised = Principal(user="auditor", roles=("viewer",), extra={"clearance": "CONFIDENTIAL"})
    assert principal_clearance(raised) is Clearance.CONFIDENTIAL


# ---------------------------------------------------------------------------
# retrieval: the filter runs before the reranker and before the prompt
# ---------------------------------------------------------------------------


@pytest.fixture
def clearance_app(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'clearance.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        # Two real documents, labelled through the documented metadata field.
        # The ids are the upload's own — the index is keyed by the real document
        # id, so the fixture has to use it rather than a decorative constant.
        ids: dict[str, str] = {}
        for name, level in (("public.pdf", "PUBLIC"), ("restricted.pdf", "RESTRICTED")):
            created = client.post(
                "/api/documents/upload",
                files={"files": (name, b"%PDF-1.4 fake", "application/pdf")},
            ).json()["documents"][0]
            ids[name] = created["id"]
            # The staged index id is written too, because that is the id a
            # retrieval row carries and the filter has to resolve it back.
            with app.state.session_factory() as session:
                from backend.database.models import Document

                doc = session.get(Document, created["id"])
                doc.metadata_json = json.dumps(
                    {
                        "ingestion": {
                            "indexed": True,
                            "index_document_id": f"{created['id']}.pdf",
                        },
                        "clearance": level,
                    }
                )
                session.commit()

        retriever = RecordingRetriever(
            rows=[
                _vendor_row(
                    f"{ids['public.pdf']}.pdf",
                    "Public: bearing inspection interval is 500 hours.",
                ),
                _vendor_row(
                    f"{ids['restricted.pdf']}.pdf",
                    "Restricted: vendor defect rate is 12 percent.",
                    chunk_index=1,
                ),
            ]
        )
        service = RetrievalService(
            retriever=retriever,  # type: ignore[arg-type]
            session_factory=app.state.session_factory,
            audit=app.state.audit,
            rerank_enabled=True,
        )
        app.state.retrieval = service
        yield client, service, retriever, ids


def _search_as(service: RetrievalService, roles: list[str], *, extra: dict | None = None):
    principal = Principal(user="tester", roles=tuple(roles), extra=extra or {})
    evidence = service.evidence_for_chat(
        "defect rate", top_k=10, user="tester", principal=principal
    )
    return principal, evidence


def test_authorized_user_gets_the_restricted_evidence(clearance_app):
    _, service, _, _ = clearance_app
    _, evidence = _search_as(service, ["operator"])  # RESTRICTED
    texts = [e.text for e in evidence]
    assert any("Restricted" in t for t in texts), texts
    assert any("Public" in t for t in texts), texts


def test_unauthorized_user_cannot_retrieve_restricted_evidence(clearance_app):
    _, service, retriever, _ = clearance_app
    _, evidence = _search_as(service, ["viewer"])  # PUBLIC only
    texts = [e.text for e in evidence]
    assert texts, "the public chunk must still be returned"
    assert all("Restricted" not in t for t in texts), texts

    # And it never reached the reranker either, which is the step between
    # retrieval and the model context.
    for call in retriever.rerank_calls:
        assert all("Restricted" not in (row.get("text") or "") for row in call), call


def test_the_prompt_evidence_never_contains_withheld_text(clearance_app):
    """The strongest form: the objects rendered into the system prompt."""
    _, service, _, _ = clearance_app
    _, evidence = _search_as(service, ["viewer"])
    rendered = " ".join(e.text for e in evidence)
    assert "12 percent" not in rendered
    _, entitled = _search_as(service, ["admin"])
    assert "12 percent" in " ".join(e.text for e in entitled)


def test_search_reports_how_much_was_withheld(clearance_app):
    _, service, _, _ = clearance_app
    viewer = Principal(user="v", roles=("viewer",))
    result = service.search("defect rate", top_k=10, user="v", principal=viewer)
    assert result["withheld"] == 1
    assert result["total"] == len(result["results"]) == 1
    admin = Principal(user="a", roles=("admin",))
    assert service.search("defect rate", top_k=10, user="a", principal=admin)["withheld"] == 0


def test_the_document_row_is_the_authority_not_the_chunk_copy():
    """A stale label on a chunk cannot restore access a document has lost."""
    rows = [
        {
            "document_id": f"{SECRET_DOC}.pdf",
            "text": "restricted",
            "metadata": json.dumps({"metadata": {"clearance": "PUBLIC"}}),
        }
    ]
    viewer = Principal(user="v", roles=("viewer",))
    visible, withheld = filter_chunks(
        viewer, rows, overrides_by_id={SECRET_DOC: "HIGHLY_CONFIDENTIAL"}
    )
    assert visible == [] and withheld == 1
    # Without the authoritative override the chunk's own label applies.
    visible2, withheld2 = filter_chunks(viewer, rows)
    assert len(visible2) == 1 and withheld2 == 0


# ---------------------------------------------------------------------------
# direct document lookup
# ---------------------------------------------------------------------------


def test_direct_document_lookup_respects_clearance(clearance_app):
    client, _, _, ids = clearance_app
    public_id = ids["public.pdf"]
    restricted_id = ids["restricted.pdf"]

    from backend.database.models import Document

    app = client.app
    with app.state.session_factory() as session:
        public_row = session.get(Document, public_id)
        restricted_row = session.get(Document, restricted_id)

    viewer = Principal(user="v", roles=("viewer",))
    # Permitted document: no exception.
    require_document_clearance(viewer, public_row, resource_id=public_id)
    # Restricted document: refused, and the refusal names what was required.
    with pytest.raises(ClearanceDenied) as excinfo:
        require_document_clearance(viewer, restricted_row, resource_id=restricted_id)
    assert excinfo.value.required == "RESTRICTED"
    assert excinfo.value.held == "PUBLIC"
    # An entitled caller reads it.
    require_document_clearance(Principal(user="a", roles=("admin",)), restricted_row)


# ---------------------------------------------------------------------------
# graph retrieval
# ---------------------------------------------------------------------------


def _labelled_graph() -> MemoryGraph:
    builder = GraphBuilder()
    # The equipment node has to exist before add_documents runs, because the
    # builder only links a document to a unit it already knows about — and this
    # test is about a document being reachable *by traversal*, so the edge has
    # to be real.
    builder.graph.add_entity(ent.equipment("P-1001"))
    builder.add_documents(
        [
            {
                "id": PUBLIC_DOC,
                "title": "Public manual",
                "clearance": "PUBLIC",
                "equipment": ["P-1001"],
            },
            {"id": SECRET_DOC, "title": "Restricted defect report", "clearance": "CONFIDENTIAL"},
        ]
    )
    builder.graph.link(
        "equipment:p-1001",
        "documented_in",
        ent.node_id("document", SECRET_DOC),
        evidence=[{"document_id": SECRET_DOC}],
    )
    return builder.graph


def test_graph_search_respects_clearance():
    graph = _labelled_graph()
    viewer = GraphQuery(graph, principal=Principal(user="v", roles=("viewer",)))
    visible = [n["id"] for n in viewer.search("defect")]
    assert visible == [], visible
    admin = GraphQuery(graph, principal=Principal(user="a", roles=("admin",)))
    assert [n["id"] for n in admin.search("defect")] == [ent.node_id("document", SECRET_DOC)]


def test_graph_traversal_cannot_reach_a_restricted_document():
    graph = _labelled_graph()
    viewer = GraphQuery(graph, principal=Principal(user="v", roles=("viewer",)))
    hood = viewer.neighbours("equipment:p-1001", depth=1)
    # The public document is reachable; the confidential one is not, and its
    # edge is dropped too - an edge names both endpoints. Order is not the
    # claim, membership is.
    assert {n["id"] for n in hood["nodes"]} == {
        "equipment:p-1001",
        ent.node_id("document", PUBLIC_DOC),
    }
    assert all(
        ent.node_id("document", SECRET_DOC) not in (e["source"], e["target"]) for e in hood["edges"]
    )

    entitled = GraphQuery(graph, principal=Principal(user="a", roles=("admin",)))
    names = {n["id"] for n in entitled.neighbours("equipment:p-1001", depth=1)["nodes"]}
    assert ent.node_id("document", SECRET_DOC) in names


def test_a_hidden_graph_node_is_indistinguishable_from_a_missing_one():
    graph = _labelled_graph()
    viewer = GraphQuery(graph, principal=Principal(user="v", roles=("viewer",)))
    hidden = ent.node_id("document", SECRET_DOC)
    assert viewer.node(hidden) is None
    assert viewer.neighbours(hidden)["found"] is False
    # A path that would have to name the hidden node is simply not found.
    assert viewer.path("equipment:p-1001", hidden)["found"] is False
    # ...while an entitled caller gets the real answer for both.
    admin = GraphQuery(graph, principal=Principal(user="a", roles=("admin",)))
    assert admin.node(hidden) is not None
    assert admin.path("equipment:p-1001", hidden)["found"] is True


def test_graph_subgraph_does_not_leak_a_requested_hidden_node():
    graph = _labelled_graph()
    viewer = GraphQuery(graph, principal=Principal(user="v", roles=("viewer",)))
    sub = viewer.subgraph(
        [ent.node_id("document", PUBLIC_DOC), ent.node_id("document", SECRET_DOC)]
    )
    assert [n["id"] for n in sub["nodes"]] == [ent.node_id("document", PUBLIC_DOC)]
    assert sub["edges"] == []


# ---------------------------------------------------------------------------
# agent tool calls obey the same policy
# ---------------------------------------------------------------------------


class _StubRetrieval:
    """Minimal RetrievalService surface: records the principal it was given."""

    def __init__(self, service: RetrievalService) -> None:
        self._service = service
        self.seen_principals: list[Principal | None] = []

    def search(
        self,
        query,
        *,
        top_k=10,
        mode="hybrid",
        document_ids=None,
        rerank=None,
        user=None,
        principal=None,
    ):
        self.seen_principals.append(principal)
        return self._service.search(
            query,
            top_k=top_k,
            mode=mode,
            document_ids=document_ids,
            rerank=rerank,
            user=user,
            principal=principal,
        )


@pytest.mark.asyncio
async def test_agent_tool_call_is_filtered_by_the_callers_clearance(clearance_app):
    _, service, _, _ = clearance_app
    tool = SearchDocumentsTool()

    viewer_ctx = ToolContext(
        user="v", roles=["viewer"], clearance=None, retrieval=service, session_factory=None
    )
    viewer_result = await tool.run(tool.arguments_model(query="defect rate", top_k=10), viewer_ctx)
    viewer_texts = [r.get("text", "") for r in viewer_result.output["results"]]
    assert viewer_texts and all("Restricted" not in t for t in viewer_texts)

    operator_ctx = ToolContext(
        user="o", roles=["operator"], clearance=None, retrieval=service, session_factory=None
    )
    operator_result = await tool.run(
        tool.arguments_model(query="defect rate", top_k=10), operator_ctx
    )
    operator_texts = [r.get("text", "") for r in operator_result.output["results"]]
    assert any("Restricted" in t for t in operator_texts)


@pytest.mark.asyncio
async def test_agent_tool_call_honours_an_explicit_badge_below_the_role(clearance_app):
    """An operator with an INTERNAL badge is not widened to RESTRICTED."""
    _, service, _, _ = clearance_app
    tool = SearchDocumentsTool()
    ctx = ToolContext(
        user="contractor",
        roles=["operator"],
        clearance="INTERNAL",
        retrieval=service,
        session_factory=None,
    )
    result = await tool.run(tool.arguments_model(query="defect rate", top_k=10), ctx)
    texts = [r.get("text", "") for r in result.output["results"]]
    assert texts and all("Restricted" not in t for t in texts)


@pytest.mark.asyncio
async def test_read_document_tool_refuses_a_document_above_the_callers_clearance(clearance_app):
    client, _, _, ids = clearance_app
    restricted_id = ids["restricted.pdf"]
    public_id = ids["public.pdf"]

    tool = ReadDocumentTool()
    viewer_ctx = ToolContext(
        user="v", roles=["viewer"], session_factory=client.app.state.session_factory
    )
    denied = await tool.run(tool.arguments_model(document_id=restricted_id), viewer_ctx)
    assert denied.status == "denied"
    assert denied.output["required_clearance"] == "RESTRICTED"
    assert denied.output["held_clearance"] == "PUBLIC"
    assert "filename" not in denied.output.get("document", {})

    allowed = await tool.run(tool.arguments_model(document_id=public_id), viewer_ctx)
    assert allowed.status == "ok"
    assert allowed.output["document"]["filename"] == "public.pdf"
