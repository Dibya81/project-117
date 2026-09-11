"""XLSX content specs.

Records in, validated workbook spec out. The interesting work is normalising
heterogeneous records into a rectangular sheet without losing anything:

* the column set is the **union** of keys in first-seen order, so a record
  that carries an extra field does not silently drop it;
* a missing key becomes an empty cell rather than a shifted row;
* values are coerced to the four cell types the renderer accepts, and
  anything else is stringified rather than passed through to fail inside the
  sandbox;
* a leading ``=``, ``+``, ``-`` or ``@`` is prefixed with an apostrophe. Excel
  treats those as formulas, and a value that came from a document must never
  become executable content in a spreadsheet a human then opens.

Rendering happens in the sandbox through ``create_xlsx``; see
:mod:`backend.tools.office.docx` for why that boundary is where it is.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.deliverables.spec import MAX_ROWS_PER_SHEET, SpecError, parse_spec

#: Characters Excel rejects in a sheet name.
_ILLEGAL_SHEET_CHARS = set(r"[]:*?/\\")

_FORMULA_LEADERS = ("=", "+", "-", "@")


def safe_sheet_name(name: str, *, fallback: str = "Sheet1") -> str:
    """Excel-legal sheet name: no illegal characters, at most 31 chars."""
    cleaned = "".join(" " if ch in _ILLEGAL_SHEET_CHARS else ch for ch in str(name or ""))
    cleaned = " ".join(cleaned.split()).strip()
    return (cleaned or fallback)[:31]


def cell(value: Any) -> str | float | int | bool | None:
    """Coerce one value into an allowed cell type, defusing formulas."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if text[:1] in _FORMULA_LEADERS:
        # Not a rejection: the value is preserved, it just cannot execute.
        return "'" + text
    return text


def columns_of(records: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for record in records:
        for key in record:
            if str(key) not in seen:
                seen.append(str(key))
    return seen


def sheet_from_records(
    name: str,
    records: Sequence[Mapping[str, Any]],
    *,
    columns: Sequence[str] | None = None,
    freeze_header: bool = True,
) -> dict[str, Any]:
    """Build one sheet from a list of dicts."""
    rows = [dict(record) for record in records or []]
    header = [str(col) for col in (columns or columns_of(rows))]
    if not header:
        raise SpecError(f"sheet '{name}' has no columns; supply records or columns")
    if len(rows) > MAX_ROWS_PER_SHEET:
        raise SpecError(
            f"sheet '{name}' has {len(rows)} rows; the limit is {MAX_ROWS_PER_SHEET}. "
            "Aggregate first, or split across sheets."
        )
    return {
        "name": safe_sheet_name(name),
        "columns": header,
        "rows": [[cell(row.get(col)) for col in header] for row in rows],
        "freeze_header": bool(freeze_header),
    }


def sheet_from_grid(
    name: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    freeze_header: bool = True,
) -> dict[str, Any]:
    """Build one sheet from positional rows, checking the width as we go."""
    header = [str(col) for col in columns]
    if not header:
        raise SpecError(f"sheet '{name}' needs at least one column")
    grid: list[list[Any]] = []
    for index, row in enumerate(rows or []):
        values = list(row)
        if len(values) != len(header):
            raise SpecError(
                f"sheet '{name}' row {index + 1} has {len(values)} cells, "
                f"expected {len(header)}"
            )
        grid.append([cell(value) for value in values])
    return {
        "name": safe_sheet_name(name),
        "columns": header,
        "rows": grid,
        "freeze_header": bool(freeze_header),
    }


def workbook_spec(
    *,
    title: str,
    sheets: Sequence[Mapping[str, Any]],
    subtitle: str = "",
    author: str = "Project 117",
    sources: Sequence[Mapping[str, Any]] = (),
    footer: str = "",
) -> dict[str, Any]:
    """Build and validate an XLSX spec. Sheet names are de-duplicated."""
    prepared: list[dict[str, Any]] = []
    used: set[str] = set()
    for item in sheets or []:
        entry = dict(item)
        base = safe_sheet_name(entry.get("name", ""), fallback=f"Sheet{len(prepared) + 1}")
        candidate = base
        suffix = 2
        while candidate.lower() in used:
            trimmed = base[: 31 - len(str(suffix)) - 1]
            candidate = f"{trimmed}-{suffix}"
            suffix += 1
        used.add(candidate.lower())
        entry["name"] = candidate
        prepared.append(entry)
    if not prepared:
        raise SpecError("a workbook needs at least one sheet")

    payload = {
        "type": "xlsx",
        "title": str(title),
        "subtitle": str(subtitle),
        "author": str(author),
        "sheets": prepared,
        "sources": [dict(item) for item in sources],
        "footer": str(footer),
    }
    parse_spec(payload, expected_type="xlsx")
    return payload


__all__ = [
    "cell",
    "columns_of",
    "safe_sheet_name",
    "sheet_from_grid",
    "sheet_from_records",
    "workbook_spec",
]
