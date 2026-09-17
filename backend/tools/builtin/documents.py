"""Document tools (Phase 8, over the Phase 3/4 pipeline).

Three read-only tools. They are thin on purpose: retrieval logic lives in
:class:`backend.rag.RetrievalService`, which owns the vector and lexical legs,
fusion, reranking and the id-bridging that turns index rows back into document
ids and page numbers. These tools add argument validation, scoping and output
capping - nothing else. A second retrieval path here is exactly the kind of
duplicate implementation the audit set out to avoid.

Two details that matter more than they look.

**Scoping is inherited, not invented.** If a job was submitted against
specific documents, ``context.document_ids`` carries that scope, and a tool
call that names no documents inherits it. A model cannot widen its own reach
by omitting an argument.

**Chunk text is capped per result.** Retrieval returns whole chunks; a
twenty-hit search would otherwise blow past the tool's output budget and the
model's context in one call. Truncation is marked, so the reader can tell a
short chunk from a trimmed one.

``extract_table`` deserves a note: it returns table blocks the ingestion
pipeline identified, as text, with their provenance. It does not parse them
into grids, because nothing in the current stack does that reliably and a
function that silently returns half a table is worse than one that hands over
the block and says so. Numeric work on tables belongs in ``analyze_csv``,
where the numbers are computed rather than guessed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.security.clearance import ClearanceDenied
from backend.security.clearance.access import require_document_clearance
from backend.security.rbac import Principal
from backend.tools.base import (
    Permission,
    ResourceLimits,
    RiskLevel,
    ToolArgumentError,
    ToolContext,
    ToolError,
    ToolResult,
    ToolSpec,
    ToolUnavailable,
)

#: Per-result text budget. Enough to judge relevance and quote a sentence.
MAX_CHUNK_CHARS = 1_500

_NO_RETRIEVAL = (
    "document search is unavailable: retrieval is not configured. Ingest a "
    "document first, and check the embedding model configuration."
)


def _shorten(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_CHUNK_CHARS:
        return text, False
    return text[:MAX_CHUNK_CHARS], True


def _present(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten one Evidence dict into a tool-facing result.

    ``Evidence.to_dict`` nests provenance under ``citation``. Flattening it
    here means a planner or agent reads ``page`` where it expects ``page``,
    instead of having to know the retrieval layer's internal shape.
    """
    citation = result.get("citation") or {}
    document = result.get("document") or {}
    text, truncated = _shorten(str(result.get("text") or ""))
    return {
        "chunk_id": result.get("chunk_id"),
        "document_id": citation.get("document_id"),
        "filename": document.get("filename"),
        "page": citation.get("page"),
        "section": citation.get("heading_path"),
        "block_type": citation.get("block_type"),
        "chunk_index": citation.get("chunk_index"),
        "score": result.get("score"),
        "rerank_score": result.get("rerank_score"),
        "text": text,
        "text_truncated": truncated,
    }


def _map_retrieval_error(exc: Exception) -> Exception:
    from backend.rag.errors import (
        IndexUnavailableError,
        RerankerUnavailableError,
        RetrievalError,
    )

    if isinstance(exc, (IndexUnavailableError, RerankerUnavailableError)):
        # Either the index cannot serve this request or the named documents are
        # not in it. Both mean "not answerable as asked" rather than "try the
        # same call again", so recovery replans instead of retrying.
        return ToolUnavailable(str(exc))
    if isinstance(exc, RetrievalError):
        return ToolError(str(exc))
    return ToolError(f"retrieval failed: {type(exc).__name__}: {exc}")


def _principal(context: ToolContext) -> Principal | None:
    """The caller a tool acts as, for clearance purposes.

    The tool context carries roles (and the caller's explicit badge, when they
    have one) rather than a Principal, because the registry resolves identity at
    the API boundary and passes a tool only what it needs. The badge is honoured
    when present, so a caller whose badge is *lower* than their role default is
    not silently widened by the tool path; otherwise the clearance the roles
    confer is used, which is exactly what the RBAC gate already approved.
    A context with neither roles, a user nor a badge yields ``None`` — the
    clearance layer's default, never an elevated one.
    """
    if not context.roles and not context.user and not context.clearance:
        return None
    extra = {"clearance": context.clearance} if context.clearance else {}
    return Principal(
        user=context.user or "unknown",
        roles=tuple(context.roles) or ("viewer",),
        extra=extra,
    )


async def _search(
    context: ToolContext,
    *,
    query: str,
    top_k: int,
    mode: str,
    document_ids: list[str] | None,
    rerank: bool | None = None,
) -> dict[str, Any]:
    if context.retrieval is None:
        raise ToolUnavailable(_NO_RETRIEVAL)
    try:
        # RetrievalService is synchronous (vendor code underneath), so it goes
        # to a worker thread rather than blocking the event loop.
        #
        # The clearance is derived from the tool context's roles, which the
        # registry already checked for the tool's own permission. One policy:
        # an agent's tool call is filtered by exactly the same rules as an
        # interactive search, so a tool call is not a way around clearance.
        return await asyncio.to_thread(
            context.retrieval.search,
            query,
            top_k=top_k,
            mode=mode,
            document_ids=document_ids,
            rerank=rerank,
            user=context.user,
            principal=_principal(context),
        )
    except Exception as exc:
        raise _map_retrieval_error(exc) from exc


def _scope(explicit: list[str] | None, context: ToolContext) -> list[str] | None:
    if explicit:
        return list(explicit)
    if context.document_ids:
        return list(context.document_ids)
    return None


# --- search_documents ------------------------------------------------------


class SearchDocumentsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1_000)
    top_k: int = Field(default=8, ge=1, le=50)
    mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    document_ids: list[str] | None = Field(default=None, max_length=50)
    rerank: bool | None = None


class SearchDocumentsTool:
    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="search_documents",
            description=(
                "Search the indexed documents and return passages with provenance "
                "(document_id, filename, page, section, chunk_id). Modes: 'semantic' "
                "(meaning), 'lexical' (exact terms, tag numbers, part numbers), 'hybrid' "
                "(default, both). Use one focused query per call and call it several times "
                "for several questions. Every claim in an answer must trace to a passage "
                "returned here."
            ),
            permission=Permission.SEARCH_QUERY,
            risk=RiskLevel.READ,
            limits=ResourceLimits(timeout_seconds=90.0),
            capabilities=["retrieval", "citations"],
            latency_class=2,
            cost_class=1,
            input_schema=SearchDocumentsArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "results": {"type": "array", "items": {"type": "object"}},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return SearchDocumentsArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, SearchDocumentsArguments)
        payload = await _search(
            context,
            query=arguments.query,
            top_k=arguments.top_k,
            mode=arguments.mode,
            document_ids=_scope(arguments.document_ids, context),
            rerank=arguments.rerank,
        )
        results = [_present(item) for item in payload.get("results", [])]
        return ToolResult(
            tool=self._spec.name,
            output={
                "query": arguments.query,
                "mode": payload.get("mode", arguments.mode),
                "total": len(results),
                "scoped_documents": _scope(arguments.document_ids, context) or [],
                "results": results,
            },
        )


# --- read_document ---------------------------------------------------------


class ReadDocumentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=64)
    #: What to pull from the document. Omit for metadata only.
    query: str | None = Field(default=None, max_length=1_000)
    max_chunks: int = Field(default=8, ge=1, le=30)


class ReadDocumentTool:
    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="read_document",
            description=(
                "Read one document: filename, status, size, page count and ingestion "
                "details. With 'query', also returns the passages of that document most "
                "relevant to it, in page order, with provenance. Large documents are not "
                "returned whole - ask for what you need, then cite the pages you used."
            ),
            permission=Permission.DOCUMENTS_READ,
            risk=RiskLevel.READ,
            limits=ResourceLimits(timeout_seconds=90.0),
            capabilities=["documents", "metadata"],
            latency_class=2,
            cost_class=1,
            input_schema=ReadDocumentArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "document": {"type": "object"},
                    "passages": {"type": "array", "items": {"type": "object"}},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return ReadDocumentArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ReadDocumentArguments)
        # A clearance refusal is a refusal, not an outage: the tool reports it
        # as such so the operator sees "you may not read this", and the audit
        # row records a refused outcome rather than a failed call.
        try:
            metadata = await asyncio.to_thread(self._load, arguments.document_id, context)
        except ClearanceDenied as exc:
            return ToolResult(
                tool=self._spec.name,
                status="denied",
                error=str(exc),
                output={
                    "document_id": arguments.document_id,
                    "required_clearance": exc.required,
                    "held_clearance": exc.held,
                    "reason": "clearance_denied",
                },
            )

        passages: list[dict[str, Any]] = []
        if arguments.query:
            payload = await _search(
                context,
                query=arguments.query,
                top_k=arguments.max_chunks,
                mode="hybrid",
                document_ids=[arguments.document_id],
            )
            passages = [_present(item) for item in payload.get("results", [])]
            # Page order reads like a document; score order reads like a
            # search result. For reading, page order is what a human wants.
            passages.sort(key=lambda item: (item.get("page") or 0, item.get("chunk_index") or 0))

        return ToolResult(
            tool=self._spec.name,
            output={
                "document": metadata,
                "passages": passages,
                "passage_count": len(passages),
                "note": (
                    "metadata only; pass 'query' to retrieve passages"
                    if not arguments.query
                    else ""
                ),
            },
        )

    @staticmethod
    def _load(document_id: str, context: ToolContext) -> dict[str, Any]:
        if context.session_factory is None:
            raise ToolUnavailable("document metadata is unavailable: no database session")
        from backend.database.models import Document

        with context.session_factory() as session:
            row = session.get(Document, document_id)
            if row is None:
                raise ToolArgumentError(
                    f"document '{document_id}' is not recorded; list the documents first"
                )
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except ValueError:
                metadata = {}
            # A direct lookup is a claim about one named document, so an
            # unauthorized claim is refused rather than answered with metadata.
            # The clearance layer reads the row's own label; nothing about the
            # document is returned before this passes.
            require_document_clearance(_principal(context), row, resource_id=document_id)
            ingestion = metadata.get("ingestion") or {}
            return {
                "document_id": row.id,
                "filename": row.filename,
                "status": row.status,
                "content_type": row.content_type,
                "size_bytes": row.size_bytes,
                "pages": ingestion.get("pages") or metadata.get("pages"),
                "chunks": ingestion.get("chunks"),
                "indexed": bool(ingestion.get("indexed")),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }


# --- extract_table ---------------------------------------------------------


class ExtractTableArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=64)
    #: What the table is about, e.g. "bearing clearance limits".
    query: str = Field(min_length=1, max_length=1_000)
    page: int | None = Field(default=None, ge=1)
    max_tables: int = Field(default=5, ge=1, le=20)


class ExtractTableTool:
    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="extract_table",
            description=(
                "Find table blocks in one document and return them as text with their page "
                "and section. Returns the blocks the ingestion pipeline identified as "
                "tables; it does not reshape them into rows and columns. To compute figures "
                "from a table, pass its contents to analyze_csv rather than reading numbers "
                "out by eye. Returns an empty list when no table block matches."
            ),
            permission=Permission.DOCUMENTS_READ,
            risk=RiskLevel.READ,
            limits=ResourceLimits(timeout_seconds=90.0),
            capabilities=["documents", "tables"],
            latency_class=2,
            cost_class=1,
            input_schema=ExtractTableArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "tables": {"type": "array", "items": {"type": "object"}},
                    "searched_passages": {"type": "integer"},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return ExtractTableArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ExtractTableArguments)
        # Over-fetch, because table blocks are a minority of any chunk set and
        # the retriever has no block-type filter to push this down into.
        payload = await _search(
            context,
            query=arguments.query,
            top_k=min(50, arguments.max_tables * 6),
            mode="hybrid",
            document_ids=[arguments.document_id],
        )
        candidates = [_present(item) for item in payload.get("results", [])]
        tables = [
            item
            for item in candidates
            if "table" in str(item.get("block_type") or "").lower()
            and (arguments.page is None or item.get("page") == arguments.page)
        ][: arguments.max_tables]

        note = ""
        if not tables:
            note = (
                "no table blocks matched; the figures may be in prose, or the "
                "document may have been ingested without table detection"
            )
        return ToolResult(
            tool=self._spec.name,
            output={
                "document_id": arguments.document_id,
                "tables": tables,
                "table_count": len(tables),
                "searched_passages": len(candidates),
                "note": note,
            },
        )
