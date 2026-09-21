"""Prompt injection detection and neutralization engine (Phase 2 security defense).

Detects direct prompt injections, indirect document jailbreaks, and adversarial role resets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptGuardResult:
    is_safe: bool
    risk_score: float
    violations: tuple[str, ...]
    sanitized_text: str


class PromptGuard:
    """Heuristic and regex-based guard for prompt injection and role hijacking."""

    INJECTION_PATTERNS = [
        (
            re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
            "instruction_override",
        ),
        (
            re.compile(r"disregard\s+(the\s+)?(previous|above|system)\s+prompts?", re.IGNORECASE),
            "instruction_override",
        ),
        (re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE), "system_role_hijack"),
        (re.compile(r"<\s*\|\s*im_start\s*\|\s*>", re.IGNORECASE), "chatml_token_injection"),
        (re.compile(r"\[\s*INST\s*\]", re.IGNORECASE), "llama_inst_token_injection"),
        (
            re.compile(r"jailbreak|dan\s+mode|developer\s+mode\s+enabled", re.IGNORECASE),
            "jailbreak_attempt",
        ),
        (
            re.compile(r"bypass\s+(all\s+)?(safety|security|filter)\s+checks?", re.IGNORECASE),
            "filter_bypass",
        ),
        (
            re.compile(
                r"reveal\s+(your\s+)?(secret|system\s+prompt|hidden\s+instructions?)", re.IGNORECASE
            ),
            "prompt_leakage",
        ),
    ]

    # Zero-width / invisible characters used to obfuscate text
    ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u2060\u00A0]")

    def __init__(self, risk_threshold: float = 0.5) -> None:
        self.risk_threshold = risk_threshold

    def inspect(self, text: str) -> PromptGuardResult:
        if not text:
            return PromptGuardResult(is_safe=True, risk_score=0.0, violations=(), sanitized_text="")

        cleaned = self.ZERO_WIDTH_CHARS.sub("", text)
        violations: list[str] = []
        score = 0.0

        for pattern, label in self.INJECTION_PATTERNS:
            matches = pattern.findall(cleaned)
            if matches:
                violations.append(label)
                score += 0.5 * len(matches)

        risk_score = min(1.0, score)
        is_safe = risk_score < self.risk_threshold

        # Neutralize obvious delimiters in sanitized output
        sanitized = cleaned
        for pattern, _ in self.INJECTION_PATTERNS:
            sanitized = pattern.sub("[REDACTED INJECTION ATTEMPT]", sanitized)

        return PromptGuardResult(
            is_safe=is_safe,
            risk_score=risk_score,
            violations=tuple(violations),
            sanitized_text=sanitized,
        )

    def sanitize(self, text: str) -> str:
        res = self.inspect(text)
        return res.sanitized_text
