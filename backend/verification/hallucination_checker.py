"""Fabricated-specifics checking (Phase 11).

The citation checker handles references and measured values. This checker
targets the other half of the problem, and the half that does the most damage
in a plant: **named specifics that sound authoritative and were never in the
documents.**

"Per ISO 14224, replace bearing P/N 6205-2RS on pump P-101 (see page 143)" is
four independently checkable specifics. A local model will produce that
sentence fluently whether or not any of the four appear in the corpus, and the
reader has no way to tell by looking.

The method is deliberately dumb and therefore trustworthy: extract the
specific, then look for it verbatim (normalised) in the retrieved text. No
model is asked for an opinion, because a model's opinion about whether it just
hallucinated is worth nothing.

Categories checked, chosen because each has a rigid surface form and near-zero
legitimate reason to appear un-sourced:

* **standards references** - ``ISO 14224``, ``API 610``, ``ASME B31.3``,
  ``IEC 61511``, ``EN 13306``.
* **page references** - ``page 143``, ``p. 12``. Citing a page that no
  retrieved chunk came from is a fabricated locator.
* **equipment tags** - ``P-101``, ``HX-2A``, ``V-1203`` - ISA-style loop/asset
  tags.
* **part numbers** - mixed letter/digit tokens with separators, e.g.
  ``6205-2RS``, ``MTU-4000-M63``.

Status policy:

* evidence available and the specific is absent from all of it -> **FAILED**.
  This is the one place the checker is willing to say "this is wrong" rather
  than "unconfirmed", because a token like ``6205-2RS`` either occurs in the
  corpus or does not.
* no evidence available (ungrounded chat) -> **SKIPPED**, with the count of
  specifics that could not be checked. Silence would imply verification
  happened.
* specifics all found -> **PASSED**.

Deliberately *not* checked: prose plausibility, tone, completeness. Those need
a judge, and a judge here would be a second model, which is exactly the
dependency verification exists to remove.
"""

from __future__ import annotations

import re
import time

from backend.verification.base import CheckResult, CheckStatus, VerificationInput

_STANDARD = re.compile(
    r"\b(ISO|IEC|API|ASME|ASTM|ANSI|EN|DIN|NFPA|OSHA|IEEE|BS|JIS|SAE)\s?"
    r"([0-9]{2,6}(?:[-\.:][0-9A-Za-z]{1,6})*)\b"
)
_PAGE_REF = re.compile(r"\b(?:page|pages|pg\.?|p\.)\s*([0-9]{1,4})\b", re.IGNORECASE)
_EQUIPMENT_TAG = re.compile(r"\b([A-Z]{1,4}-[0-9]{2,5}[A-Z]?)\b")
_PART_NUMBER = re.compile(r"\b([0-9]{3,6}-[0-9A-Z]{2,6}|[A-Z]{2,5}-[0-9]{2,5}-[0-9A-Z]{1,5})\b")

#: Words that look like tags but are ordinary prose in maintenance writing.
_TAG_ALLOWLIST = frozenset({"COVID-19", "ISO-9001", "IP-65", "IP-67", "UTF-8"})


def _normalise(text: str) -> str:
    """Collapse whitespace and punctuation variance before comparing.

    ``ISO 14224``, ``ISO-14224`` and ``iso14224`` are the same reference; a
    checker that treats them as different would generate false FAILEDs, and a
    noisy checker gets disabled.
    """
    return re.sub(r"[\s\-\.:_/]", "", (text or "").lower())


def _evidence_text(item: dict) -> str:
    for key in ("text", "snippet", "content", "chunk"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _evidence_pages(evidence: list[dict]) -> set[int]:
    pages: set[int] = set()
    for item in evidence:
        citation = item.get("citation")
        source = citation if isinstance(citation, dict) else item
        page = source.get("page")
        if isinstance(page, int):
            pages.add(page)
    return pages


class HallucinationChecker:
    name = "fabricated_specifics"

    async def check(self, payload: VerificationInput) -> CheckResult:
        started = time.perf_counter()
        answer = payload.answer or ""
        evidence = list(payload.evidence or [])

        specifics: list[tuple[str, str]] = []
        for match in _STANDARD.finditer(answer):
            specifics.append(("standard", f"{match.group(1)} {match.group(2)}"))
        for match in _EQUIPMENT_TAG.finditer(answer):
            token = match.group(1)
            if token.upper() not in _TAG_ALLOWLIST:
                specifics.append(("equipment_tag", token))
        for match in _PART_NUMBER.finditer(answer):
            specifics.append(("part_number", match.group(1)))

        page_claims = [int(match.group(1)) for match in _PAGE_REF.finditer(answer)]

        if not specifics and not page_claims:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message="the answer states no standards, tags, part numbers or page references",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        corpus = _normalise(" ".join(_evidence_text(item) for item in evidence))
        if not corpus:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message=(
                    f"{len(specifics) + len(page_claims)} specific reference(s) could not "
                    "be checked because no retrieved text was available"
                ),
                findings=[
                    {"type": "unchecked_specific", "kind": kind, "value": value}
                    for kind, value in specifics[:20]
                ],
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        findings: list[dict] = []
        seen: set[str] = set()
        for kind, value in specifics:
            key = f"{kind}:{_normalise(value)}"
            if key in seen:
                continue
            seen.add(key)
            if _normalise(value) not in corpus:
                findings.append({"type": "fabricated_specific", "kind": kind, "value": value})

        pages = _evidence_pages(evidence)
        if pages:
            for page in sorted(set(page_claims)):
                if page not in pages:
                    findings.append(
                        {
                            "type": "page_not_retrieved",
                            "kind": "page_reference",
                            "value": page,
                            "retrieved_pages": sorted(pages)[:20],
                        }
                    )

        checked = len(seen) + len(set(page_claims))
        if findings:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"{len(findings)} of {checked} specific reference(s) do not occur in "
                    "the retrieved documents"
                ),
                findings=findings[:30],
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        return CheckResult(
            checker=self.name,
            status=CheckStatus.PASSED,
            message=f"all {checked} specific reference(s) occur in the retrieved documents",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
