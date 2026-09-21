"""Causal assertion hedging for observational data analysis.

Language models frequently jump from statistical association in tabular data to
unqualified causal claims ("X caused Y", "proves that A caused B"). In industrial
operations, unverified causal claims can trigger misguided maintenance actions.
This module detects overconfident causal assertions and applies appropriate
scientific qualifiers.
"""

from __future__ import annotations

import re
from typing import Tuple, List

# Patterns matching overconfident causal language
_CAUSAL_PATTERNS = [
    (re.compile(r"\bproves\s+that\b", re.IGNORECASE), "suggests that"),
    (re.compile(r"\bdefinitely\s+(caused|led\s+to)\b", re.IGNORECASE), "is strongly correlated with"),
    (re.compile(r"\bconclusively\s+proves\b", re.IGNORECASE), "provides evidence of an association with"),
    (re.compile(r"\bdirectly\s+caused\s+by\b", re.IGNORECASE), "associated with"),
    (re.compile(r"\bproves\s+causation\b", re.IGNORECASE), "indicates statistical correlation (observational)"),
    (re.compile(r"\bis\s+the\s+sole\s+cause\s+of\b", re.IGNORECASE), "is a primary correlated factor in"),
]


def hedge_causal_claims(text: str) -> Tuple[str, List[str]]:
    """Inspect and hedge overconfident causal claims in data analysis prose.

    Returns the hedged text and a list of modifications made.
    """
    if not text:
        return text, []

    hedged = text
    applied: List[str] = []

    for pattern, replacement in _CAUSAL_PATTERNS:
        matches = pattern.findall(hedged)
        if matches:
            applied.append(f"Hedged causal assertion: '{matches[0]}' -> '{replacement}'")
            hedged = pattern.sub(replacement, hedged)

    return hedged, applied
