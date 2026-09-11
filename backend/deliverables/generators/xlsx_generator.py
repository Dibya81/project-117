"""Excel generator - runs inside the sandbox.

    python xlsx_generator.py --spec inputs/spec.json --out artifacts/book.xlsx

One deliberate omission: **no formulas.** The spec model does not carry them
and this generator does not write them. A formula supplied by a language model
is executable content that a spreadsheet evaluates on the recipient's machine,
and "the model wrote a formula that looked right" is exactly the class of
error this architecture exists to remove. Numbers are computed in the sandbox
by ``run_python``, checked by the calculation checker, and written here as
values.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

#: Excel's hard limit is 32,767 characters per cell.
MAX_CELL_CHARS = 32_000


def _coerce(value: object) -> object:
    """Make a JSON value safe for a cell without changing its meaning."""
    if value is None or isinstance(value, (int, float, bool, datetime, date)):
        return value
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        text = text[:MAX_CELL_CHARS]
    # A leading '=' (or '+', '-', '@') is interpreted as a formula. Prefix with
    # an apostrophe so the cell shows the text the model actually produced
    # rather than executing it.
    if text[:1] in ("=", "+", "@") or text[:2] == "-=":
        return "'" + text
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an ArtifactSpec as .xlsx")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        print(
            "openpyxl is not installed in this sandbox image. Build the documents "
            "image (infrastructure/docker/sandbox-documents.Dockerfile) and set "
            "P117_SANDBOX_DOCUMENTS_IMAGE.",
            file=sys.stderr,
        )
        return 3

    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)

    workbook = Workbook()
    workbook.remove(workbook.active)
    written = []

    for sheet_spec in spec.get("sheets") or []:
        name = str(sheet_spec.get("name", "Sheet"))[:31]
        sheet = workbook.create_sheet(title=name)
        columns = [str(column) for column in sheet_spec.get("columns") or []]
        sheet.append(columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in sheet_spec.get("rows") or []:
            sheet.append([_coerce(value) for value in row])
        if sheet_spec.get("freeze_header", True):
            sheet.freeze_panes = "A2"
        for index, column in enumerate(columns, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(len(column) + 2, 12), 60
            )
        written.append({"sheet": name, "rows": sheet.max_row - 1, "columns": len(columns)})

    sources = spec.get("sources") or []
    if sources:
        sheet = workbook.create_sheet(title="Sources")
        sheet.append(["document_id", "page", "section", "chunk_id"])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for citation in sources:
            sheet.append(
                [
                    _coerce(citation.get("document_id")),
                    _coerce(citation.get("page")),
                    _coerce(citation.get("section")),
                    _coerce(citation.get("chunk_id")),
                ]
            )
        written.append({"sheet": "Sources", "rows": len(sources), "columns": 4})

    if not workbook.sheetnames:
        print("spec contained no sheets", file=sys.stderr)
        return 2

    workbook.save(args.out)
    print(json.dumps({"artifact": args.out, "sheets": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
