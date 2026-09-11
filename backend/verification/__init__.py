"""Verification (Phase 11).

A separate stage, with its own inputs and its own veto. Generation produces;
verification decides whether what was produced may be called a result.

The checkers are exported individually so a deployment can compose its own
set - a site with no artifact generation has no reason to pay for the artifact
checker - but the default set from :func:`default_checkers` is what the
orchestrator wires, and dropping a checker is a decision somebody has to make
explicitly in configuration rather than something that happens by omission.
"""

from backend.verification.artifact_checker import ArtifactChecker
from backend.verification.base import (
    Checker,
    CheckResult,
    CheckStatus,
    VerificationInput,
    VerificationReport,
)
from backend.verification.calculation_checker import CalculationChecker
from backend.verification.citation_checker import CitationChecker
from backend.verification.evidence_checker import EvidenceChecker
from backend.verification.hallucination_checker import HallucinationChecker
from backend.verification.policy_checker import PolicyChecker
from backend.verification.verifier import (
    DEFAULT_CHECK_TIMEOUT_SECONDS,
    Verifier,
    default_checkers,
)

__all__ = [
    "DEFAULT_CHECK_TIMEOUT_SECONDS",
    "ArtifactChecker",
    "CalculationChecker",
    "CheckResult",
    "CheckStatus",
    "Checker",
    "CitationChecker",
    "EvidenceChecker",
    "HallucinationChecker",
    "PolicyChecker",
    "VerificationInput",
    "VerificationReport",
    "Verifier",
    "default_checkers",
]
