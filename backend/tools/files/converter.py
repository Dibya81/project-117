"""Deterministic conversions between text data formats.

Everything here is pure: text in, text out, no filesystem and no model. That
is the point - a conversion that a model performs by rewriting the data is a
conversion that can silently lose a row, and there is no way to tell
afterwards. These functions either convert the data or raise.

Supported pairs are the ones the operations workflows actually need:
``csv``/``tsv`` <-> ``json``/``jsonl``, and Markdown tables (which is how
models and documents tend to present tabular data) into ``csv``/``json``.

Converting *document* formats (PDF -> text, DOCX -> text) is not here and
will not be: that is :mod:`backend.ingestion`.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Sequence

from backend.tools.base import ToolArgumentError

FORMATS = ("csv", "tsv", "json", "jsonl", "markdown")

#: Rows above this are refused rather than truncated - a converter that drops
#: data quietly is worse than one that says the input is too big.
MAX_ROWS = 50_000

_DELIMITERS = {"csv": ",", "tsv": "\t"}


def _normalise_format(name: str) -> str:
    value = str(name or "").strip().lower().lstrip(".")
    aliases = {"ndjson": "jsonl", "md": "markdown", "text/csv": "csv"}
    value = aliases.get(value, value)
    if value not in FORMATS:
        raise ToolArgumentError(f"unsupported format '{name}'; supported: {', '.join(FORMATS)}")
    return value


def _cell(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _columns_of(rows: Sequence[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(str(key))
    return seen


# --- parsing ---------------------------------------------------------------


def parse(text: str, source_format: str) -> list[dict[str, Any]]:
    """Parse ``text`` into a list of records."""
    fmt = _normalise_format(source_format)
    body = str(text or "")
    if fmt in _DELIMITERS:
        reader = csv.DictReader(io.StringIO(body), delimiter=_DELIMITERS[fmt])
        if reader.fieldnames is None:
            return []
        rows = []
        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise ToolArgumentError(f"input exceeds {MAX_ROWS} rows")
            rows.append({key: row.get(key) for key in reader.fieldnames})
        return rows
    if fmt == "json":
        try:
            parsed = json.loads(body or "[]")
        except ValueError as exc:
            raise ToolArgumentError(f"input is not valid JSON: {exc}") from exc
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ToolArgumentError(f"expected an array of objects, got {type(parsed).__name__}")
        return [item for item in parsed if isinstance(item, dict)]
    if fmt == "jsonl":
        rows = []
        for index, line in enumerate(body.splitlines()):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise ToolArgumentError(f"line {index + 1} is not valid JSON: {exc}") from exc
            if isinstance(item, dict):
                rows.append(item)
        return rows
    return parse_markdown_table(body)


def parse_markdown_table(text: str) -> list[dict[str, Any]]:
    """Parse the first GitHub-style pipe table in ``text``.

    Separator rows (``|---|---|``) are skipped, leading/trailing pipes are
    optional, and a row with the wrong number of cells is reported with its
    line number rather than padded into place.
    """
    lines = [line.strip() for line in str(text or "").splitlines()]
    table = [line for line in lines if line.startswith("|") or ("|" in line and line)]
    if not table:
        raise ToolArgumentError("no pipe-delimited table was found in the input")

    def split(line: str) -> list[str]:
        cleaned = line.strip()
        if cleaned.startswith("|"):
            cleaned = cleaned[1:]
        if cleaned.endswith("|"):
            cleaned = cleaned[:-1]
        return [cell.strip() for cell in cleaned.split("|")]

    header = split(table[0])
    rows: list[dict[str, Any]] = []
    for offset, line in enumerate(table[1:], start=2):
        cells = split(line)
        if all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        if len(cells) != len(header):
            raise ToolArgumentError(
                f"table row {offset} has {len(cells)} cells but the header has "
                f"{len(header)}; fix the table rather than guessing"
            )
        rows.append(dict(zip(header, cells)))
    return rows


# --- rendering -------------------------------------------------------------


def render(
    rows: Sequence[dict[str, Any]], target_format: str, *, columns: Sequence[str] | None = None
) -> str:
    """Render records into ``target_format``."""
    fmt = _normalise_format(target_format)
    records = [dict(row) for row in rows or []]
    header = list(columns or _columns_of(records))
    if fmt in _DELIMITERS:
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=header, delimiter=_DELIMITERS[fmt], extrasaction="ignore"
        )
        writer.writeheader()
        for row in records:
            writer.writerow({key: _cell(row.get(key)) for key in header})
        return buffer.getvalue()
    if fmt == "json":
        return json.dumps(records, ensure_ascii=False, indent=2, default=str) + "\n"
    if fmt == "jsonl":
        return "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in records)
    widths = [len(str(col)) for col in header]
    for row in records:
        for index, col in enumerate(header):
            widths[index] = max(widths[index], len(str(row.get(col, ""))))
    out = [
        "| " + " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(header)) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(header))) + " |",
    ]
    for row in records:
        out.append(
            "| "
            + " | ".join(str(row.get(col, "")).ljust(widths[i]) for i, col in enumerate(header))
            + " |"
        )
    return "\n".join(out) + "\n"


def convert(
    text: str,
    *,
    source_format: str,
    target_format: str,
    columns: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Convert ``text`` between two supported formats.

    Returns the converted text plus the row/column counts, so a caller can
    assert that nothing was lost instead of trusting that nothing was.
    """
    source = _normalise_format(source_format)
    target = _normalise_format(target_format)
    records = parse(text, source)
    output = render(records, target, columns=columns)
    return {
        "source_format": source,
        "target_format": target,
        "row_count": len(records),
        "columns": list(columns or _columns_of(records)),
        "text": output,
        "bytes": len(output.encode("utf-8")),
    }


__all__ = [
    "FORMATS",
    "MAX_ROWS",
    "convert",
    "parse",
    "parse_markdown_table",
    "render",
]
