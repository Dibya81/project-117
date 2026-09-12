"""Document retrieval for the simulation's Documentation agent.

The red-team audit found the Documentation agent citing a literal
``source_id="SOP-14.2"`` for every incident on every plant, with the
``retrieve_documents`` tool recorded in the trace but never executed. This
module replaces that with retrieval that actually runs.

Two backends, one interface:

* ``LocalGPTBackend`` — the project's real retrieval stack
  (``backend.rag.RetrievalService`` over the vendored localGPT LanceDB index:
  vector + FTS legs, RRF fusion, reranking). Used whenever the vendor package
  and the index are importable.
* ``LexicalCorpusBackend`` — an on-prem BM25 index built directly over the
  *ingested LanceDB table* that ``scripts/ingest_corpus.py`` fills from the
  real ``data/corpus/`` documents (PDF/DOCX/PPTX/XLSX). No embeddings, no
  network, no vendor dependency, so it is the offline-safe leg. It no longer
  walks a hand-maintained markdown directory (the synthetic ``data/knowledge``
  and ``data/demo`` corpora are gone); if the LanceDB table is absent it simply
  indexes nothing and the caller degrades visibly instead of crashing.

Both return the same ``RetrievedChunk`` records (document id, chunk id,
source path, text, metadata, citation), so the agent code never branches on
which one served the query. Crucially, **neither one can return a constant**:
the query is built from the failing equipment kind, measurement, failure
mechanism and process area, so different assets retrieve different documents.
If no backend can serve a query the agent records a failed tool call and the
Documentation task is marked ``blocked`` — it never invents a citation.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

#: LanceDB index produced by the ingestion pipeline (``scripts/ingest_corpus.py``).
#: Configurable to match ``P117_LANCEDB_DIR`` / ``P117_LANCEDB_TABLE``.
LANCEDB_DIR = Path(os.environ.get("P117_LANCEDB_DIR", "data/lancedb"))
LANCEDB_TABLE = os.environ.get("P117_LANCEDB_TABLE", "p117_chunks")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-\.]*")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "is", "are", "be",
    "with", "at", "by", "as", "it", "this", "that", "from", "shall", "must", "if",
}


@dataclass
class RetrievedChunk:
    """One retrieved passage. Every field is produced by the backend."""

    document_id: str
    chunk_id: str
    source: str
    title: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def citation(self) -> str:
        return f"{self.document_id}#{self.chunk_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "source": self.source,
            "title": self.title,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "citation": self.citation,
        }


class RetrievalBackend(Protocol):
    name: str

    def search(self, query: str, k: int = 3, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]: ...

    def document_count(self) -> int: ...


# --------------------------------------------------------------- lexical BM25


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _load_lancedb_rows(db_path: Path, table_name: str) -> list[dict[str, Any]]:
    """Rows from the ingested LanceDB table, or ``[]`` when it is not there.

    Importing lancedb is deliberately guarded: a deployment without the vendor
    stack must still import this module and degrade visibly (zero documents)
    rather than crash.
    """
    try:
        import lancedb  # noqa: PLC0415
    except Exception:  # ImportError or a broken native wheel
        return []
    try:
        db = lancedb.connect(str(db_path))
        if table_name not in db.table_names():
            return []
        return db.open_table(table_name).to_arrow().to_pylist()
    except Exception:  # missing table, corrupt index, unreadable directory
        return []


def _chunk_from_row(row: dict[str, Any]) -> RetrievedChunk:
    document_id = str(row.get("document_id") or "")
    chunk_index = row.get("chunk_index")
    chunk_id = str(row.get("chunk_id") or f"{document_id}_{chunk_index}")
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    inner = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else meta
    heading = inner.get("heading_path") or []
    title = str(heading[-1]) if heading else str(inner.get("document_name") or document_id)
    source = str(inner.get("source") or document_id)
    return RetrievedChunk(
        document_id=document_id or source,
        chunk_id=chunk_id,
        source=source,
        title=title or document_id,
        text=str(row.get("text") or ""),
        score=0.0,
        metadata=meta,
    )


class LexicalCorpusBackend:
    """BM25 over the ingested LanceDB corpus. Deterministic and offline."""

    name = "lexical-bm25"
    k1 = 1.5
    b = 0.75

    def __init__(self, db_path: Path | None = None, table_name: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else LANCEDB_DIR
        self.table_name = table_name or LANCEDB_TABLE
        self.chunks: list[RetrievedChunk] = []
        self._tokens: list[Counter] = []
        self._lengths: list[int] = []
        self._df: Counter = Counter()
        self._docs: set[str] = set()
        self._index()

    # -- indexing

    def _index(self) -> None:
        for row in _load_lancedb_rows(self.db_path, self.table_name):
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            chunk = _chunk_from_row(row)
            self._docs.add(chunk.document_id)
            toks = Counter(
                _tokenize(
                    f"{chunk.title} {text} "
                    f"{' '.join(str(v) for v in chunk.metadata.values())}"
                )
            )
            self.chunks.append(chunk)
            self._tokens.append(toks)
            self._lengths.append(sum(toks.values()) or 1)
            for term in toks:
                self._df[term] += 1
        self._avgdl = (sum(self._lengths) / len(self._lengths)) if self._lengths else 1.0

    # -- query

    def document_count(self) -> int:
        return len(self._docs)

    def search(self, query: str, k: int = 3, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        if not self.chunks:
            return []
        q = _tokenize(query)
        if not q:
            return []
        n = len(self.chunks)
        scored: list[tuple[float, int]] = []
        for idx, toks in enumerate(self._tokens):
            if filters and not _matches(self.chunks[idx].metadata, filters):
                continue
            dl = self._lengths[idx]
            s = 0.0
            for term in q:
                f = toks.get(term, 0)
                if not f:
                    continue
                df = self._df.get(term, 0) or 1
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
            if s > 0:
                scored.append((s, idx))
        scored.sort(key=lambda p: (-p[0], self.chunks[p[1]].document_id, self.chunks[p[1]].chunk_id))
        out: list[RetrievedChunk] = []
        seen_docs: set[str] = set()
        for s, idx in scored:
            c = self.chunks[idx]
            if c.document_id in seen_docs:  # one best passage per document
                continue
            seen_docs.add(c.document_id)
            out.append(
                RetrievedChunk(
                    document_id=c.document_id, chunk_id=c.chunk_id, source=c.source,
                    title=c.title, text=c.text, score=s, metadata=dict(c.metadata),
                )
            )
            if len(out) >= k:
                break
        return out


# ------------------------------------------------------------ localGPT bridge


class LocalGPTBackend:
    """Adapter onto ``backend.rag.RetrievalService`` (localGPT + LanceDB)."""

    name = "localgpt-lancedb"

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def try_build(cls) -> "LocalGPTBackend | None":
        if os.environ.get("P117_SIM_RETRIEVAL", "auto") == "lexical":
            return None
        try:  # the vendor stack is optional; see docs/SETUP.md
            from backend.rag import RetrievalService  # noqa: PLC0415
            from backend.rag.adapter import LocalGPTRetriever  # noqa: PLC0415

            retriever = LocalGPTRetriever()
            service = RetrievalService(retriever=retriever)
        except Exception:  # ImportError, VendorNotAvailableError, index missing
            return None
        return cls(service)

    def document_count(self) -> int:
        try:
            return int(len(self._service._document_names_for()))
        except Exception:
            return 0

    def search(self, query: str, k: int = 3, filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        results = self._service.search(query=query, k=k)
        out: list[RetrievedChunk] = []
        for i, ev in enumerate(results or []):
            d = ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
            out.append(
                RetrievedChunk(
                    document_id=str(d.get("document_id") or d.get("id") or f"doc-{i}"),
                    chunk_id=str(d.get("chunk_id") or d.get("chunk") or f"c{i:03d}"),
                    source=str(d.get("source") or d.get("document_name") or ""),
                    title=str(d.get("title") or d.get("document_name") or ""),
                    text=str(d.get("text") or d.get("content") or ""),
                    score=float(d.get("score") or 0.0),
                    metadata=dict(d.get("metadata") or {}),
                )
            )
        return out


# ---------------------------------------------------------------- front door


class RetrievalUnavailable(RuntimeError):
    """Raised when no retrieval backend can serve a query."""


class SimulationRetriever:
    """Picks the best available backend once, then serves queries."""

    def __init__(self, backend: RetrievalBackend | None = None) -> None:
        self.backend = backend or LocalGPTBackend.try_build() or LexicalCorpusBackend()

    @property
    def name(self) -> str:
        return self.backend.name

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def document_count(self) -> int:
        return self.backend.document_count()

    def for_incident(
        self,
        *,
        equipment_kind: str,
        equipment_tag: str,
        measurement: str | None,
        mechanism: str | None,
        area: str | None,
        k: int = 3,
    ) -> tuple[str, list[RetrievedChunk]]:
        """Build the query from real incident context and run it.

        The query string is returned alongside the hits so the agent trace can
        show exactly what was asked — no hidden prompt, no chain-of-thought.
        """
        parts = [equipment_kind]
        if mechanism:
            parts.append(mechanism.replace("_", " "))
        if measurement:
            parts.append(f"{measurement} instrument")
        if area:
            parts.append(area.replace("-", " "))
        parts.append("procedure isolation inspection")
        query = " ".join(p for p in parts if p)
        if os.environ.get("P117_SIM_RETRIEVAL_DISABLE") == "1":
            # Failure-path switch used by tests and by operators verifying that
            # a missing knowledge base blocks the documentation task instead of
            # quietly inventing a citation.
            raise RetrievalUnavailable("retrieval disabled via P117_SIM_RETRIEVAL_DISABLE")
        hits = self.backend.search(query, k=k)
        if not hits and mechanism:  # one broadening retry, still query-driven
            hits = self.backend.search(f"{equipment_kind} {mechanism.replace('_', ' ')}", k=k)
        if not hits:
            raise RetrievalUnavailable(f"no documents matched: {query!r}")
        return query, hits


def _matches(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(str(meta.get(k, "")).lower() == str(v).lower() for k, v in filters.items())


_retriever: SimulationRetriever | None = None


def get_retriever() -> SimulationRetriever:
    global _retriever
    if _retriever is None:
        _retriever = SimulationRetriever()
    return _retriever
