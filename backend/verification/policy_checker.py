"""Policy checking (Phase 11 + Phase 12).

The other checkers ask "is this answer true?". This one asks "is this answer
*allowed to be sent*?" - a separate question with a separate failure mode, and
the one that matters most in a plant that adopted an on-premise system
specifically so that confidential content stays put.

Three things are checked, in descending order of severity.

**1. Credential leakage (FAILED).** Industrial documents contain service
accounts, VPN details, PLC passwords and license keys. Retrieval will happily
surface that chunk, and a model will happily quote it into a report that then
gets emailed around. Detected credential shapes block completion outright. The
matched value is never written into the finding - a verification record that
quotes the leaked key has simply moved the leak into the audit log.

**2. Dropped safety notices (WARNING).** If the retrieved evidence carries
DANGER / WARNING / CAUTION text and the generated procedure carries none, the
model has summarised away the part that keeps someone's hands attached. This
is not a hallucination - every sentence may be accurate - which is exactly why
no other checker catches it. It is a warning rather than a failure because
some tasks legitimately do not reproduce procedure text.

**3. Claimed external sources (WARNING).** An answer that cites a vendor
website or "the latest online documentation" contradicts the deployment's zero
egress guarantee: either the model invented the source, or something reached
the network. Both need a human to look.

What this checker deliberately does not do is enforce authorisation. Whether
this user may read this document was decided before retrieval ran, by RBAC.
Re-deciding it here would be a second, weaker copy of that logic.
"""

from __future__ import annotations

import re
import time

from backend.verification.base import CheckResult, CheckStatus, VerificationInput

#: Credential shapes, kept narrow so ordinary engineering text does not match.
#: Each entry is (label, pattern).
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.=]{20,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    (
        "assigned_password",
        re.compile(
            r"\b(?:password|passwd|passcode|api[_ -]?key|secret|token)\b\s*[:=]\s*"
            r"[^\s\"']{6,}",
            re.IGNORECASE,
        ),
    ),
    ("connection_string", re.compile(r"\b[a-z][a-z0-9+\.\-]*://[^\s/@]+:[^\s/@]+@", re.I)),
)

#: Patterns whose *shape* is already conclusive: nothing but a credential
#: looks like a PEM block, an AKIA id or a JWT. For these, a soft placeholder
#: word is not an excuse - AWS's own documentation key contains "EXAMPLE", and
#: treating that as a placeholder would let a whole class of real keys through
#: any document that happens to use the word. Only a fragment that is visibly
#: a template (angle brackets, braces, xxxxxx) is suppressed.
_STRICT_KINDS = frozenset(
    {
        "private_key_block",
        "aws_access_key_id",
        "openai_style_key",
        "bearer_token",
        "jwt",
        "connection_string",
    }
)

#: Template markers, for the strict patterns above.
_TEMPLATE_MARKER = re.compile(
    r"(?:<[^>]{1,40}>|\{\{?[a-z_ ]{1,40}\}?\}|x{6,}|\*{6,}|redacted)",
    re.IGNORECASE,
)

#: Placeholders that look like credentials but are documentation, not secrets.
#: Applied only to the loose "password: value" pattern, where "secret: example"
#: really is documentation rather than a leak.
_SECRET_PLACEHOLDERS = re.compile(
    r"(?:<[^>]{1,40}>|\{\{?[a-z_ ]{1,40}\}?\}|x{6,}|\*{6,}|redacted|your[_ -]?(?:key|password)|"
    r"example|changeme|placeholder|n/?a)",
    re.IGNORECASE,
)

_SAFETY_TERMS = re.compile(
    r"\b(danger|warning|caution|hazard|lock ?out|tag ?out|loto|de-?energi[sz]e|"
    r"confined space|arc flash|ppe|permit to work|isolation|explosive|toxic|asphyxiat)",
    re.IGNORECASE,
)

#: Answer wording that implies a procedure is being handed to somebody.
_PROCEDURE_TERMS = re.compile(
    r"\b(step \d|procedure|first,|then,|remove the|install the|disconnect|open the valve|"
    r"tighten|torque to|start the|shut ?down|restart)\b",
    re.IGNORECASE,
)

_EXTERNAL_CLAIMS = re.compile(
    r"\b(?:according to|per|from|see)\s+(?:the\s+)?"
    r"(?:manufacturer'?s? (?:website|site|portal)|vendor (?:website|portal)|online (?:documentation|manual)|"
    r"internet|web search|google|wikipedia|latest (?:online|web) )"
    r"|\bhttps?://",
    re.IGNORECASE,
)


def _evidence_text(item: dict) -> str:
    for key in ("text", "snippet", "content", "chunk"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


class PolicyChecker:
    name = "policy"

    async def check(self, payload: VerificationInput) -> CheckResult:
        started = time.perf_counter()
        answer = payload.answer or ""
        evidence = list(payload.evidence or [])
        findings: list[dict] = []

        # 1. credential leakage -> blocking
        leaks: list[dict] = []
        for label, pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(answer):
                fragment = match.group(0)
                suppress = (
                    _TEMPLATE_MARKER.search(fragment)
                    if label in _STRICT_KINDS
                    else _SECRET_PLACEHOLDERS.search(fragment)
                )
                if suppress:
                    continue
                # Record where, and how long - never what.
                leaks.append(
                    {
                        "type": "credential_in_output",
                        "kind": label,
                        "offset": match.start(),
                        "length": len(fragment),
                    }
                )
        if leaks:
            return CheckResult(
                checker=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"{len(leaks)} credential-shaped value(s) appear in the output; "
                    "the result is blocked and the values are not recorded here"
                ),
                findings=leaks[:20],
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        status = CheckStatus.PASSED
        checked_anything = False

        # 2. safety notices present in the source but not in the answer
        if evidence and _PROCEDURE_TERMS.search(answer):
            checked_anything = True
            source_terms = {
                match.group(0).lower()
                for item in evidence
                for match in _SAFETY_TERMS.finditer(_evidence_text(item))
            }
            if source_terms and not _SAFETY_TERMS.search(answer):
                status = CheckStatus.WARNING
                findings.append(
                    {
                        "type": "safety_notice_dropped",
                        "source_terms": sorted(source_terms)[:10],
                        "hint": (
                            "the retrieved procedure carries safety notices that the "
                            "generated text does not repeat"
                        ),
                    }
                )

        # 3. claimed external sources, which contradict zero-egress operation
        external = [match.group(0)[:80] for match in _EXTERNAL_CLAIMS.finditer(answer)]
        if external:
            checked_anything = True
            status = CheckStatus.WARNING
            findings.append(
                {
                    "type": "external_source_claimed",
                    "references": external[:10],
                    "hint": (
                        "this deployment does not reach the network; either the source "
                        "was invented or egress needs investigating"
                    ),
                }
            )

        # Artifacts inherit the same rule: a deck may not carry credentials
        # either. Their text is checked by the artifact checker inside the
        # sandbox; here we only note that they exist and were policy-scanned
        # at the answer level.
        if payload.artifacts:
            checked_anything = True

        if not checked_anything and not answer.strip():
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message="there is no output to apply output policy to",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        message = (
            "no credential leakage, dropped safety notices or external-source claims found"
            if status is CheckStatus.PASSED
            else "output policy concerns found that need a human to look"
        )
        return CheckResult(
            checker=self.name,
            status=status,
            message=message,
            findings=findings,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
