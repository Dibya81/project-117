"""Citation checking (Phase 11).

Answers the question the review put first: *does the citation the answer gives
actually exist, and does the chunk it names contain what the sentence claims?*

The chain checked here is exactly the one the review specified::

    claim -> retrieved chunk -> document_id -> page -> heading -> exists?

Three failures are distinguished, because they have different causes and
different fixes:

``dangling citation``
    The answer cites ``[7]`` when six passages were retrieved. The citation
    cannot be checked because its target does not exist. **FAILED** - this is
    a fabricated reference, and it is the single most damaging failure mode
    for a document assistant, because the citation is what makes the reader
    stop verifying.

``uncited claim``
    The answer states a specific figure - a torque, a pressure, a set point,
    a page - with no citation anywhere in the sentence, while evidence was
    available. **FAILED** when the figure also cannot be found in any
    retrieved chunk, **WARNING** when it can (present in the evidence but the
    model did not attribute it).

``unsupported citation``
    The citation exists but the chunk it points at shares almost no content
    with the sentence. Reported as **WARNING**, not FAILED: lexical overlap is
    a weak proxy for entailment, and this checker refuses to claim a
    certainty it cannot justify. Judging entailment would require a model,
    and a model's opinion is exactly what verification is not allowed to rest
    on.

When no evidence was retrieved at all the check is **SKIPPED** rather than
passed. "Nothing to check" and "checked and correct" must never collapse into
the same status.
"""

from __future__ import annotations

import re
import time

from backend.verification.base import CheckResult, CheckStatus, VerificationInput

#: ``[1]``, ``[2, 3]``, ``[1][4]`` - the shapes local models actually emit.
_CITATION = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]")

#: Prose page references: "(page 143)", "p. 12", "pages 8-9". The demo task
#: asks the model to cite source pages, so this is the citation form it will
#: actually produce - a checker that only understood ``[1]`` markers would
#: report every correctly-cited answer as uncited, and a checker that cries
#: wolf is a checker that gets switched off.
_PAGE_REF = re.compile(
    r"\b(?:pages?|pp?\.)\s*(\d{1,5})(?:\s*[-\u2013]\s*(\d{1,5}))?",
    re.IGNORECASE,
)

#: Numbers that carry engineering meaning: a bare "3" in "3 steps" is noise,
#: but "3.5 bar", "250 Nm", "page 143" are claims a reader will act on.
_MEASUREMENT = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*"
    r"(nm|n·m|kn|kg|g|mm|cm|m|km|in|ft|bar|psi|kpa|mpa|pa|°c|°f|c|f|k|"
    r"rpm|hz|khz|v|kv|a|ma|kw|mw|w|l|ml|%|ppm|mm/s|m/s|hours?|hrs?|minutes?|min)\b",
    re.IGNORECASE,
)

#: How much of a sentence's vocabulary must appear in the cited chunk before
#: the citation is considered corroborated. Low on purpose - a paraphrase
#: shares few words - because the goal is to catch citations pointing at
#: unrelated text, not to grade writing style.
_OVERLAP_THRESHOLD = 0.18

_STOPWORDS = frozenset(
    """a an and are as at be been but by can for from had has have how in into is it its
    may must not of on or should than that the their then there these this those to was
    were what when where which who will with would you your""".split()
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [part.strip() for part in parts if part.strip()]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9\-/\.]{2,}", (text or "").lower())
    return {word for word in words if word not in _STOPWORDS}


def _evidence_text(item: dict) -> str:
    for key in ("text", "snippet", "content", "chunk"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _evidence_meta(item: dict) -> dict:
    """Provenance for one evidence dict.

    ``rag.service.Evidence.to_dict`` nests provenance under ``citation``
    (``document_id``, ``chunk_index``, ``page``, ``heading_path``,
    ``block_type``). Older/flattened shapes put it at the top level, so both
    are accepted - a checker that silently reported ``page: None`` because it
    looked in the wrong place would be worse than useless.
    """
    citation = item.get("citation")
    source = citation if isinstance(citation, dict) else item
    return {
        "chunk_id": item.get("chunk_id"),
        "document_id": source.get("document_id") or item.get("document_id"),
        "page": source.get("page") if source.get("page") is not None else item.get("page"),
        "heading_path": source.get("heading_path") or item.get("heading_path") or [],
    }


class CitationChecker:
    name = "citations"

    async def check(self, payload: VerificationInput) -> CheckResult:
        started = time.perf_counter()
        answer = payload.answer or ""
        evidence = list(payload.evidence or [])

        if not evidence:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message="no evidence was retrieved, so citations could not be checked",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        if not answer.strip():
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message="the result has no prose answer to check citations in",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        findings: list[dict] = []
        worst = CheckStatus.PASSED
        evidence_all = " ".join(_evidence_text(item) for item in evidence)
        evidence_available = bool(evidence_all.strip())
        cited_any = False

        # Which pages were actually retrieved, and at which position, so a
        # prose page reference can be resolved back to the chunk it names.
        retrieved_pages: dict[int, list[int]] = {}
        for position, item in enumerate(evidence, start=1):
            page = _evidence_meta(item).get("page")
            if isinstance(page, int):
                retrieved_pages.setdefault(page, []).append(position)
        pages_known = bool(retrieved_pages)

        for sentence in _sentences(answer):
            indices: list[int] = []
            for match in _CITATION.finditer(sentence):
                for part in match.group(1).split(","):
                    try:
                        indices.append(int(part.strip()))
                    except ValueError:  # pragma: no cover - regex guards this
                        continue

            # 1. dangling citations
            for index in indices:
                cited_any = True
                if index < 1 or index > len(evidence):
                    worst = CheckStatus.FAILED
                    findings.append(
                        {
                            "type": "dangling_citation",
                            "citation": index,
                            "available": len(evidence),
                            "sentence": sentence[:200],
                        }
                    )

            valid = [i for i in indices if 1 <= i <= len(evidence)]

            # 1b. prose page references, checked against the pages that were
            # actually retrieved. A page number nobody retrieved is the same
            # fabrication as a dangling ``[7]`` and a more dangerous one, since
            # "see page 143" is precisely the kind of detail a reader accepts
            # without opening the document.
            for match in _PAGE_REF.finditer(sentence):
                for group in match.groups():
                    if not group:
                        continue
                    page = int(group)
                    if not pages_known:
                        # The retrieved chunks carry no page metadata, so the
                        # reference cannot be checked either way. Count it as
                        # an attribution and claim nothing about it.
                        cited_any = True
                        continue
                    if page in retrieved_pages:
                        cited_any = True
                        # Resolve to the chunk(s) on that page so the support
                        # check below reads the text the answer points at.
                        valid.extend(retrieved_pages[page])
                    else:
                        worst = CheckStatus.FAILED
                        findings.append(
                            {
                                "type": "page_not_retrieved",
                                "page": page,
                                "retrieved_pages": sorted(retrieved_pages)[:20],
                                "sentence": sentence[:200],
                            }
                        )

            # 2. uncited measurements
            measurements = [m.group(0) for m in _MEASUREMENT.finditer(sentence)]
            if measurements and not valid:
                in_evidence = all(
                    re.search(re.escape(value.split()[0]), evidence_all) for value in measurements
                )
                if evidence_available and not in_evidence:
                    worst = CheckStatus.FAILED
                    findings.append(
                        {
                            "type": "uncited_value_not_in_evidence",
                            "values": measurements[:5],
                            "sentence": sentence[:200],
                        }
                    )
                else:
                    if worst is CheckStatus.PASSED:
                        worst = CheckStatus.WARNING
                    findings.append(
                        {
                            "type": "uncited_value",
                            "values": measurements[:5],
                            "sentence": sentence[:200],
                        }
                    )

            # 3. citation exists but does not look related
            for index in sorted(set(valid)):
                item = evidence[index - 1]
                chunk = _evidence_text(item)
                if not chunk:
                    if worst is CheckStatus.PASSED:
                        worst = CheckStatus.WARNING
                    findings.append(
                        {
                            "type": "evidence_text_unavailable",
                            "citation": index,
                            **_evidence_meta(item),
                        }
                    )
                    continue
                sentence_tokens = _tokens(_CITATION.sub("", sentence))
                if not sentence_tokens:
                    continue
                overlap = len(sentence_tokens & _tokens(chunk)) / len(sentence_tokens)
                if overlap < _OVERLAP_THRESHOLD:
                    if worst is CheckStatus.PASSED:
                        worst = CheckStatus.WARNING
                    findings.append(
                        {
                            "type": "weak_support",
                            "citation": index,
                            **_evidence_meta(item),
                            "overlap": round(overlap, 3),
                            "sentence": sentence[:200],
                        }
                    )

        if not cited_any:
            # Evidence was retrieved and used, and the answer cites nothing.
            # A reader cannot check any of it.
            worst = CheckStatus.FAILED if evidence_available else CheckStatus.WARNING
            findings.append(
                {
                    "type": "no_citations",
                    "evidence_available": len(evidence),
                }
            )

        message = {
            CheckStatus.PASSED: f"all citations resolve to retrieved evidence ({len(evidence)} passages)",
            CheckStatus.WARNING: "citations resolve, but some claims are weakly supported or unattributed",
            CheckStatus.FAILED: "the answer cites evidence that does not exist or states figures absent from the evidence",
        }[worst]

        return CheckResult(
            checker=self.name,
            status=worst,
            message=message,
            findings=findings[:50],
            duration_ms=(time.perf_counter() - started) * 1000,
        )
