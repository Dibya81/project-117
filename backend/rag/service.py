"""Retrieval service (Phase 4).

Orchestrates one search:

    validate → compile filters (localGPT DSL) → hybrid retrieval (vendor) →
    optional rerank → map staged basenames back to document UUIDs → resolve
    document rows → audit

Design rules (mirroring the ingestion service):
- One implementation per responsibility: this service owns *orchestration and
  identity bridging*, the adapter owns *vendor plumbing*, localGPT owns *the
  retrieval logic*. Nothing here re-implements search.
- **UUID↔index bridging.** Ingestion stages documents as ``<uuid><ext>``
  symlinks, so LanceDB rows carry ``document_id == "<uuid><ext>"``. This
  service strips the extension to resolve the API-level document id, and
  translates client-side ``document_ids`` (UUIDs) into the staged basenames
  the index knows.
- **Citation metadata preserved.** Every evidence item carries
  ``document_id``, ``page``, ``heading_path``, ``block_type``,
  ``chunk_index`` — exactly what Phase 3 promised and what the frontend will
  cite. The metadata lives one level down in the row JSON (localGPT's
  VectorIndexer stores the full chunk dict as the ``metadata`` column).
- **Fail loud on filters.** A filter that cannot be compiled is a 400, never
  a silently unfiltered search. A request scoped to documents that are not
  indexed is a 404-class ``IndexUnavailableError`` with the offending ids —
  not an empty result.
- Audit events carry ids/counts/durations, never raw document content.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from sqlalchemy.orm import sessionmaker

from backend.database.models import Document
from backend.rag.adapter import LocalGPTRetriever, ensure_vendor_available
from backend.rag.errors import IndexUnavailableError, RerankerUnavailableError, RetrievalError
from backend.security.clearance import Clearance, clearance_of
from backend.security.clearance.access import filter_chunks
from backend.security.rbac import Principal

logger = logging.getLogger(__name__)


class Citation:
    """A structured citation for one evidence chunk."""

    __slots__ = ("document_id", "chunk_index", "page", "heading_path", "block_type")

    def __init__(
        self,
        *,
        document_id: str,
        chunk_index: int,
        page: int | None,
        heading_path: list[str],
        block_type: str,
    ) -> None:
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.page = page
        self.heading_path = heading_path
        self.block_type = block_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "heading_path": self.heading_path,
            "block_type": self.block_type,
        }


class Evidence:
    """One retrieved chunk, with citation metadata, scores and source filename."""

    __slots__ = ("chunk_id", "text", "score", "rerank_score", "citation", "document_filename")

    def __init__(
        self,
        *,
        chunk_id: str,
        text: str,
        score: float,
        rerank_score: float | None,
        citation: Citation,
        document_filename: str | None,
    ) -> None:
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.rerank_score = rerank_score
        self.citation = citation
        self.document_filename = document_filename

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "rerank_score": self.rerank_score,
            "citation": self.citation.to_dict(),
        }
        if self.document_filename is not None:
            out["document"] = {"id": self.citation.document_id, "filename": self.document_filename}
        return out


class RetrievalService:
    def __init__(
        self,
        *,
        retriever: LocalGPTRetriever,
        session_factory: sessionmaker,
        audit: Any,
        rerank_enabled: bool = True,
        rerank_candidates: int = 30,
    ) -> None:
        self._retriever = retriever
        self._session_factory = session_factory
        self._audit = audit
        self._rerank_enabled = rerank_enabled
        self._rerank_candidates = rerank_candidates

    # --- public API -------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        mode: str = "hybrid",
        document_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        rerank: bool | None = None,
        user: str | None = None,
        principal: Principal | None = None,
    ) -> dict[str, Any]:
        """Run one search and return ``{query, mode, total, results, ...}``.

        ``document_ids`` scopes the search to UUID document rows (each must
        exist; scoping to a not-indexed document is an error, not silence).
        ``filters`` is localGPT's metadata filter DSL (document_id /
        document_name / chunk_id / chunk_index) applied on top.

        ``principal`` is the caller whose clearance the results are filtered
        against. The filter runs **before the reranker and before any
        ``Evidence`` object is built**, which is what keeps unauthorized text
        out of the model context rather than merely out of the response: a
        reranker scores the text it is given, and a prompt cites the evidence
        it is handed. ``withheld`` in the response counts what was removed, so
        "nothing matched" and "something matched that you may not see" are
        distinguishable by the caller.
        """
        started = time.perf_counter()

        # Compile the where-clause first: a bad filter must fail before any
        # vendor I/O, and unknown document ids must fail before retrieval.
        where = self._compile_where(filters, document_ids)

        try:
            rows = self._retriever.retrieve(query, top_k=top_k, mode=mode, where=where)
        except RetrievalError:
            raise
        except Exception as exc:  # noqa: BLE001 — vendor errors become typed failures
            raise RetrievalError(str(exc)) from exc

        # Clearance, before anything else touches the content. A retrieved chunk
        # carries its document's label; the authoritative record is the document
        # row, so that label is read first and the chunk's own metadata is the
        # fallback for rows whose document has no label.
        labels = self._clearance_labels_for(rows)
        rows, withheld = filter_chunks(principal, rows, overrides_by_id=labels)
        if withheld:
            logger.info("retrieval withheld %d chunk(s) above the caller's clearance", withheld)

        if rerank is None:
            rerank = self._rerank_enabled
        if rerank and rows:
            try:
                rows = self._retriever.rerank(query, rows[: self._rerank_candidates], top_k=top_k)
            except Exception as exc:  # noqa: BLE001
                raise RerankerUnavailableError(str(exc)) from exc

        results = self._bridge_and_resolve(rows)
        elapsed = time.perf_counter() - started

        self._audit.record(
            action="search.performed",
            resource_type="search",
            user=user,
            detail={
                "mode": mode,
                "top_k": top_k,
                "reranked": bool(rerank and rows),
                "results": len(results),
                "withheld_by_clearance": withheld,
                "scoped_documents": len(document_ids or []),
                "elapsed_seconds": round(elapsed, 2),
            },
        )
        return {
            "query": query,
            "mode": mode,
            "total": len(results),
            "withheld": withheld,
            "results": [e.to_dict() for e in results],
            "elapsed_seconds": round(elapsed, 2),
        }

    def evidence_for_chat(
        self,
        query: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
        user: str | None = None,
        principal: Principal | None = None,
    ) -> list[Evidence]:
        """Retrieval used to ground a chat turn (Phase 4 chat grounding).

        Best-effort by design: chat must still answer when nothing is indexed
        or retrieval fails — the caller receives ``[]`` instead of an error.
        Scoped ids that don't exist are still a loud client error (400).

        Clearance is not best-effort: an authorized-only result set is the
        contract, and the filter is applied inside :meth:`search` before the
        evidence is built, so a failure to filter cannot be swallowed into
        "the model answered without context".
        """
        if document_ids:
            self._require_documents(document_ids)
        try:
            payload = self.search(
                query,
                top_k=top_k,
                mode="hybrid",
                document_ids=document_ids,
                rerank=self._rerank_enabled,
                user=user,
                principal=principal,
            )
        except RetrievalError as exc:
            logger.warning("chat grounding skipped: %s", exc)
            return []
        return [self._evidence_from_dict(r) for r in payload["results"]]

    # --- internals ---------------------------------------------------------

    def _compile_where(
        self,
        filters: dict[str, Any] | None,
        document_ids: list[str] | None,
    ) -> str | None:
        """Compile the final LanceDB where-clause.

        ``document_ids`` are API-level UUIDs; the index keys rows by the
        staged basename ``<uuid><ext>``, so scoping compiles to a
        ``document_id in (...)`` predicate over basenames resolved from the
        document rows (unknown UUIDs raise 404-class, never pass silently).
        The user filter DSL is compiled by localGPT's ``compile_filters``.
        """
        # Import via the vendored tree (the adapter owns sys.path); lazily,
        # so app boot/tests never import the vendor package.
        ensure_vendor_available()
        from rag_system.retrieval.filters import FilterError, compile_filters

        spec: dict[str, Any] = dict(filters or {})
        if document_ids:
            # _staged_names_for raises IndexUnavailableError for unknown or
            # not-indexed UUIDs — a scoped search never silently widens.
            spec["document_id"] = {"in": self._staged_names_for(document_ids)}
        try:
            compiled = compile_filters(spec or None)
        except FilterError as exc:
            raise RetrievalError(f"invalid filters: {exc}") from exc
        return compiled.where if compiled is not None else None

    def _clearance_labels_for(self, rows: list[dict[str, Any]]) -> dict[str, Clearance]:
        """Authoritative document clearance, keyed by every id a row may carry.

        One query per search, over just the documents the search touched. The
        document row is the authority — a chunk's copied metadata can be stale
        the moment an operator raises a document's clearance — so this is read
        first and the chunk metadata is only a fallback.

        The staged name (``<uuid><ext>``) and the bare UUID are both keyed, so
        the filter matches regardless of which one a row carries. A document
        that cannot be resolved contributes no key and the chunk's own label
        applies, which is the conservative direction.
        """
        ids: set[str] = set()
        for row in rows:
            raw = str(row.get("document_id") or "")
            if not raw:
                continue
            ids.add(raw)
            if "." in raw:
                ids.add(raw.rsplit(".", 1)[0])
        if not ids:
            return {}
        with self._session_factory() as session:
            documents = session.query(Document).filter(Document.id.in_(sorted(ids))).all()
        labels: dict[str, Clearance] = {}
        for doc in documents:
            try:
                metadata = json.loads(doc.metadata_json or "{}")
            except ValueError:
                metadata = {}
            level = clearance_of(metadata)
            labels[doc.id] = level
            staged = ((metadata.get("ingestion") or {}).get("index_document_id")) or ""
            if staged:
                labels[str(staged)] = level
        return labels

    def _staged_names_for(self, document_ids: list[str]) -> list[str]:
        """Staged basenames (``<uuid><ext>``) for UUIDs that are indexed.

        The staged name is recorded in ``metadata.ingestion.index_document_id``
        at reindex time; fall back to the row's own extension for documents
        indexed before that field existed.
        """
        with self._session_factory() as session:
            rows = session.query(Document).filter(Document.id.in_(document_ids)).all()
            by_id = {row.id: row for row in rows}

        missing = [doc_id for doc_id in document_ids if doc_id not in by_id]
        if missing:
            raise IndexUnavailableError(
                f"documents not found: {', '.join(sorted(missing))}"
            )

        staged: list[str] = []
        not_indexed: list[str] = []
        for doc_id in document_ids:
            row = by_id[doc_id]
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except ValueError:
                metadata = {}
            ingestion = metadata.get("ingestion") or {}
            index_document_id = ingestion.get("index_document_id")
            if ingestion.get("indexed") and index_document_id:
                staged.append(str(index_document_id))
                continue
            not_indexed.append(doc_id)

        if not_indexed:
            raise IndexUnavailableError(
                f"documents not indexed: {', '.join(sorted(not_indexed))} — "
                "POST /api/documents/{id}/reindex"
            )
        # Sanity: the staged basename must be "<uuid>.<ext>" — refuse ids
        # carrying characters the vendor's SQL predicates would choke on.
        for name in staged:
            if not re.fullmatch(r"[0-9a-fA-F-]{36}\.[A-Za-z0-9]+", name):
                raise RetrievalError(f"refusing malformed index id for a document: {name!r}")
        return staged

    def _bridge_and_resolve(self, rows: list[dict[str, Any]]) -> list[Evidence]:
        """Rows → Evidence: strip the staged extension back to the UUID and
        resolve document filenames for citations."""
        id_map = self._document_names_for()
        results: list[Evidence] = []
        for row in rows:
            staged = str(row.get("document_id") or "")
            # Ingestion stages every document as "<uuid><ext>", so the index's
            # document_id is that basename; the API-level id is the stem.
            document_id = staged.rsplit(".", 1)[0] if "." in staged else staged
            metadata = row.get("metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (TypeError, ValueError):
                    metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
            # localGPT's VectorIndexer stores the full chunk dict as JSON in
            # the metadata column: {text, metadata: {page, heading_path, ...}}.
            nested = metadata.get("metadata")
            inner: dict[str, Any] = nested if isinstance(nested, dict) else metadata
            page = inner.get("page")
            heading_path = inner.get("heading_path") or []
            if not isinstance(heading_path, list):
                heading_path = []
            citation = Citation(
                document_id=document_id,
                chunk_index=int(row.get("chunk_index", -1)),
                page=int(page) if isinstance(page, (int, float)) else None,
                heading_path=[str(h) for h in heading_path],
                block_type=str(inner.get("block_type") or "paragraph"),
            )
            results.append(
                Evidence(
                    chunk_id=str(row.get("chunk_id") or ""),
                    text=str(row.get("text") or ""),
                    score=float(row.get("score") or 0.0),
                    rerank_score=(
                        float(row["rerank_score"]) if row.get("rerank_score") is not None else None
                    ),
                    citation=citation,
                    document_filename=id_map.get(document_id),
                )
            )
        return results

    def _document_names_for(self) -> dict[str, str]:
        """UUID → original filename map (one query, cached per call)."""
        with self._session_factory() as session:
            rows = session.query(Document).all()
        return {row.id: row.filename for row in rows}

    def _require_documents(self, document_ids: list[str]) -> None:
        from sqlalchemy import select

        with self._session_factory() as session:
            found = set(session.scalars(select(Document.id).where(Document.id.in_(document_ids))))
        missing = sorted(set(document_ids) - found)
        if missing:
            raise IndexUnavailableError(f"documents not found: {', '.join(missing)}")

    def _evidence_from_dict(self, data: dict[str, Any]) -> Evidence:
        citation = Citation(
            document_id=data["citation"]["document_id"],
            chunk_index=data["citation"]["chunk_index"],
            page=data["citation"]["page"],
            heading_path=data["citation"]["heading_path"],
            block_type=data["citation"]["block_type"],
        )
        return Evidence(
            chunk_id=data["chunk_id"],
            text=data["text"],
            score=data["score"],
            rerank_score=data.get("rerank_score"),
            citation=citation,
            document_filename=(data.get("document") or {}).get("filename"),
        )
