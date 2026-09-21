"""Logging configuration with automatic sensitive data redaction.

Scrubs API keys, bearer tokens, private keys, passwords, and other secret patterns
from both log records and formatted exception tracebacks (exc_info / exc_text).
"""

from __future__ import annotations

import json
import logging
import re
import sys

# Sensitive regex patterns to redact
_SENSITIVE_PATTERNS = [
    # API keys / generic secret tokens
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
        ),
        r"\1=[REDACTED]",
    ),
    # OpenAI-style keys
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"), "[REDACTED_API_KEY]"),
    # Bearer tokens
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{15,}"), "Bearer [REDACTED_TOKEN]"),
    # Passwords in URLs, JSON, key-value
    (
        re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s,;'\"]{4,})['\"]?"),
        r"\1=[REDACTED]",
    ),
    # Private keys
    (
        re.compile(
            r"-----BEGIN [A-Z\s]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z\s]+ PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # Authorization header
    (re.compile(r"(?i)authorization:\s*[^\r\n]+"), "Authorization: [REDACTED]"),
]


def redact_text(text: str) -> str:
    """Scrub sensitive patterns from arbitrary string."""
    if not text:
        return text
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts secrets from record messages, args, and tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact main message if it's a string
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)

        # Redact formatted args if string
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_text(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    redact_text(a) if isinstance(a, str) else a for a in record.args
                )

        # Redact exception text if already formatted
        if getattr(record, "exc_text", None):
            record.exc_text = redact_text(record.exc_text)

        # Redact stack_info if present
        if getattr(record, "stack_info", None):
            record.stack_info = redact_text(record.stack_info)

        return True


class JSONFormatter(logging.Formatter):
    """Simple structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging(level: str | int = "INFO", json_logs: bool = False) -> None:
    """Configure root logger with SensitiveDataFilter and standard or JSON format."""
    if isinstance(level, str):
        log_level = getattr(logging, level.upper(), logging.INFO)
    else:
        log_level = level

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
        )

    handler.addFilter(SensitiveDataFilter())
    root.addHandler(handler)


def configure_logging(level: int = logging.INFO) -> None:
    setup_logging(level=level)
