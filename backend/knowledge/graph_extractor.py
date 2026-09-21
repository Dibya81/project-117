"""Knowledge-graph entity extractor.

Runs *after* a document has been indexed by the localGPT pipeline.  It reads
the indexed chunks from LanceDB via the existing ``IngestionService.chunks``
call and calls the Ollama model gateway with a structured-output prompt to
extract entity/relationship triples.

Design constraints
------------------
* **Incremental** — only the new document's chunks are processed; no full
  graph rebuild.
* **Ollama-optional** — if the gateway is unavailable or the model returns
  malformed JSON the extractor logs a warning and stores zero entities rather
  than raising.  The document is still ``indexed``; graph building is
  best-effort.
* **No hallucinations exported** — confidence < 0.4 rows are discarded before
  persisting so only plausible extractions reach the UI.
* **Provenance** — every ``KnowledgeEntity`` row links back to the document
  and chunk that produced it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import sessionmaker

from backend.database.models import KnowledgeEntity

logger = logging.getLogger(__name__)

# Industrial-domain entity types the model is guided to look for.
ENTITY_TYPES = [
    "Equipment",
    "Sensor",
    "SOP",
    "WorkOrder",
    "Material",
    "Supplier",
    "Inspection",
    "ProcessUnit",
    "MaintenanceRecord",
    "Specification",
    "Person",
    "Location",
]

_EXTRACTION_PROMPT = """\
You are an industrial knowledge graph extractor.
Given the text below from document "{filename}", extract ALL named entities and their relationships.

Entity types to look for: {entity_types}

Return ONLY valid JSON in exactly this format (no markdown, no explanation):
{{
  "entities": [
    {{
      "name": "P-102",
      "type": "Equipment",
      "aliases": ["Pump P-102", "pump 102"],
      "relationships": [
        {{"rel": "has_sensor", "target": "Vibration Sensor VS-102", "confidence": 0.9}},
        {{"rel": "governed_by", "target": "SOP-MEC-042", "confidence": 0.85}}
      ],
      "confidence": 0.95
    }}
  ]
}}

Rules:
- Only extract entities clearly present in the text.
- confidence is a float 0.0-1.0 indicating how certain you are.
- Omit entities with confidence below 0.4.
- Relationships must have both rel and target populated.
- Return empty entities list if no entities are found.

Text (chunk {chunk_index} of {total_chunks}):
{text}
"""

# Max characters per chunk sent to the model — keeps latency bounded.
_MAX_CHUNK_CHARS = 2000
# Max chunks processed per document to cap total extraction time.
_MAX_CHUNKS_PER_DOC = 30
# Minimum confidence to persist an entity.
_MIN_CONFIDENCE = 0.4


class GraphExtractor:
    """Post-ingestion entity extractor backed by the Ollama gateway."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        model_gateway: Any,  # backend.models.gateway.ModelGateway
        extraction_model: str = "llama3",
    ) -> None:
        self._sf = session_factory
        self._gw = model_gateway
        self._model = extraction_model

    def extract_and_store(
        self,
        *,
        document_id: str,
        workspace_id: str,
        filename: str,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Extract entities from *chunks* and persist them.

        Returns the number of entity rows stored.  Never raises — failures are
        logged and result in 0 rows so the caller can continue.
        """
        # Remove stale extractions for this document so a reindex is clean.
        self._purge(document_id)

        usable = chunks[:_MAX_CHUNKS_PER_DOC]
        total = len(usable)
        all_entities: list[KnowledgeEntity] = []

        for idx, chunk in enumerate(usable):
            text = (chunk.get("text") or chunk.get("content") or "").strip()
            if not text:
                continue
            text = text[:_MAX_CHUNK_CHARS]
            try:
                rows = self._extract_chunk(
                    text=text,
                    filename=filename,
                    chunk_index=idx,
                    total_chunks=total,
                    document_id=document_id,
                    workspace_id=workspace_id,
                )
                all_entities.extend(rows)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "entity extraction failed for doc=%s chunk=%d: %s",
                    document_id, idx, exc,
                )

        if all_entities:
            with self._sf() as session:
                session.add_all(all_entities)
                session.commit()
            logger.info(
                "graph extractor: stored %d entities for doc=%s",
                len(all_entities), document_id,
            )

        return len(all_entities)

    def _extract_chunk(
        self,
        *,
        text: str,
        filename: str,
        chunk_index: int,
        total_chunks: int,
        document_id: str,
        workspace_id: str,
    ) -> list[KnowledgeEntity]:
        prompt = _EXTRACTION_PROMPT.format(
            filename=filename,
            entity_types=", ".join(ENTITY_TYPES),
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            text=text,
        )

        raw = self._call_model(prompt)
        parsed = _parse_json(raw)
        if not parsed:
            return []

        rows: list[KnowledgeEntity] = []
        for ent in parsed.get("entities", []):
            name = (ent.get("name") or "").strip()
            etype = (ent.get("type") or "Unknown").strip()
            conf = float(ent.get("confidence") or 0.0)
            aliases = ent.get("aliases") or []
            if not name or conf < _MIN_CONFIDENCE:
                continue

            # Base entity node (no relationship)
            rows.append(
                KnowledgeEntity(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    entity_type=etype,
                    name=name,
                    aliases_json=json.dumps(aliases),
                    rel_type=None,
                    target_name=None,
                    source_chunk=chunk_index,
                    confidence=conf,
                )
            )

            # Relationship edges
            for rel in ent.get("relationships") or []:
                rel_type = (rel.get("rel") or "").strip()
                target = (rel.get("target") or "").strip()
                rel_conf = float(rel.get("confidence") or conf)
                if rel_type and target and rel_conf >= _MIN_CONFIDENCE:
                    rows.append(
                        KnowledgeEntity(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            entity_type=etype,
                            name=name,
                            aliases_json=json.dumps(aliases),
                            rel_type=rel_type,
                            target_name=target,
                            source_chunk=chunk_index,
                            confidence=rel_conf,
                        )
                    )

        return rows

    def _call_model(self, prompt: str) -> str:
        """Call the model gateway and return raw text.

        Uses a synchronous chat completion path.  Falls back to empty string
        on any error so the caller can handle it gracefully.
        """
        try:
            # ModelGateway.complete is the sync call used by tool handlers.
            result = self._gw.complete(
                role="reasoning",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
            )
            # Result may be a string or a dict with "content"/"text".
            if isinstance(result, str):
                return result
            if isinstance(result, dict):
                return result.get("content") or result.get("text") or ""
        except Exception as exc:  # noqa: BLE001
            logger.debug("model call failed: %s", exc)
        return ""

    def _purge(self, document_id: str) -> None:
        from sqlalchemy import delete
        with self._sf() as session:
            session.execute(
                delete(KnowledgeEntity).where(
                    KnowledgeEntity.document_id == document_id
                )
            )
            session.commit()

    def purge_workspace(self, workspace_id: str) -> None:
        """Remove all entity rows for a workspace (used on workspace delete)."""
        from sqlalchemy import delete
        with self._sf() as session:
            session.execute(
                delete(KnowledgeEntity).where(
                    KnowledgeEntity.workspace_id == workspace_id
                )
            )
            session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> dict | None:
    """Try to parse a JSON object from a model response.

    Models occasionally wrap the JSON in markdown code fences; this strips
    them before parsing.
    """
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find the first { … } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
