"""Evidence checking (Phase 11).

The citation checker asks "does the reference the answer gives resolve?". This
checker asks the prior question: **was there anything to cite, and is the
provenance complete enough for a human to go and look?**

That distinction matters because the two failures have different owners. A
dangling ``[7]`` is a model failure. Evidence arriving without a page number
is an *ingestion* failure - the chunk was indexed without page metadata - and
no amount of prompting will fix it. Reporting them separately is what makes
the difference actionable.

What is checked:

* **grounded answer with no evidence** - the job claimed retrieval was used and
  retrieval returned nothing, yet an answer was still produced. FAILED: this
  is the shape of a confidently hallucinated answer.
* **incomplete provenance** - evidence without ``document_id``, without a page
  and without a heading path. WARNING, with the offending chunk ids, because
  the answer may still be correct while being unverifiable by hand.
* **empty chunk text** - an index that returned ids but no content. WARNING;
  it also silently weakens the citation checker, so it is worth surfacing.
* **degenerate scores** - every retrieval score identical or zero, which in
  practice means the reranker or the vector index is misconfigured rather than
  that the corpus is uniform. WARNING.
* **document scope** - evidence drawn from documents the request did not ask
  for is reported by the policy checker, not here.

No model is consulted. Every judgement above is a property of the retrieval
result itself.
"""

from __future__ import annotations

import time

from backend.verification.base import CheckResult, CheckStatus, VerificationInput

#: Below this, an "answer" is a refusal or a status line, and demanding
#: evidence for it would be noise.
_MIN_ANSWER_CHARS = 200

#: Phrases a grounded model uses when it correctly declines. If the answer is
#: an explicit refusal, missing evidence is the *expected* outcome, not a
#: failure - punishing it would train the system to answer anyway.
_REFUSAL_MARKERS = (
    "not in these documents",
    "not present in the provided",
    "no evidence",
    "could not find",
    "not found in the",
    "does not appear in",
    "cannot answer",
    "no relevant",
    "insufficient information",
)


def _text(item: dict) -> str:
    for key in ("text", "snippet", "content", "chunk"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _provenance(item: dict) -> dict:
    citation = item.get("citation")
    source = citation if isinstance(citation, dict) else item
    return {
        "chunk_id": item.get("chunk_id"),
        "document_id": source.get("document_id") or item.get("document_id"),
        "page": source.get("page") if source.get("page") is not None else item.get("page"),
        "heading_path": source.get("heading_path") or item.get("heading_path") or [],
    }


def _is_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


class EvidenceChecker:
    name = "evidence"

    async def check(self, payload: VerificationInput) -> CheckResult:
        started = time.perf_counter()
        answer = (payload.answer or "").strip()
        evidence = list(payload.evidence or [])
        findings: list[dict] = []

        if not evidence:
            if not answer or len(answer) < _MIN_ANSWER_CHARS or _is_refusal(answer):
                return CheckResult(
                    checker=self.name,
                    status=CheckStatus.SKIPPED,
                    message=(
                        "no evidence was retrieved and the answer does not assert "
                        "document-based findings"
                    ),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            return CheckResult(
                checker=self.name,
                status=CheckStatus.FAILED,
                message=(
                    "a substantive answer was produced with no retrieved evidence "
                    "behind it"
                ),
                findings=[{"type": "answer_without_evidence", "answer_chars": len(answer)}],
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        status = CheckStatus.PASSED

        incomplete = []
        empty = []
        for item in evidence:
            meta = _provenance(item)
            if not meta["document_id"] or (meta["page"] is None and not meta["heading_path"]):
                incomplete.append(meta)
            if not _text(item):
                empty.append({"chunk_id": meta["chunk_id"], "document_id": meta["document_id"]})

        if incomplete:
            status = CheckStatus.WARNING
            findings.append(
                {
                    "type": "incomplete_provenance",
                    "count": len(incomplete),
                    "of": len(evidence),
                    "chunks": incomplete[:10],
                    "hint": "re-ingest the source document; page/heading metadata is missing",
                }
            )
        if empty:
            status = CheckStatus.WARNING
            findings.append(
                {
                    "type": "empty_chunk_text",
                    "count": len(empty),
                    "chunks": empty[:10],
                    "hint": "the index returned ids without content; citations cannot be corroborated",
                }
            )

        scores = [
            item.get("rerank_score") if item.get("rerank_score") is not None else item.get("score")
            for item in evidence
        ]
        numeric = [float(value) for value in scores if isinstance(value, (int, float))]
        if len(numeric) >= 3 and len(set(numeric)) == 1:
            status = CheckStatus.WARNING if status is CheckStatus.PASSED else status
            findings.append(
                {
                    "type": "degenerate_scores",
                    "value": numeric[0],
                    "hint": "identical scores across passages usually means retrieval scoring is misconfigured",
                }
            )

        documents = {
            _provenance(item)["document_id"]
            for item in evidence
            if _provenance(item)["document_id"]
        }
        message = {
            CheckStatus.PASSED: (
                f"{len(evidence)} passages from {len(documents)} document(s) carry "
                "complete provenance"
            ),
            CheckStatus.WARNING: (
                f"{len(evidence)} passages retrieved, but some provenance is incomplete "
                "or the index looks misconfigured"
            ),
        }[status]

        return CheckResult(
            checker=self.name,
            status=status,
            message=message,
            findings=findings,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
