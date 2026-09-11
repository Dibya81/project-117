"""Office-format content builders.

These modules build *validated content specs*; the files themselves are
rendered by reviewed generators inside the documents sandbox image, reached
through the ``create_docx`` / ``create_xlsx`` / ``create_pptx`` /
``create_pdf`` tools. Keeping construction and rendering apart means there is
exactly one code path that can produce a deliverable, and it is the one that
hashes, stores, verifies and audits what it produced.
"""

from __future__ import annotations

from backend.tools.office.docx import bullet as document_bullet
from backend.tools.office.docx import (
    citation,
    document_spec,
    section,
)
from backend.tools.office.docx import from_findings as document_from_findings
from backend.tools.office.pptx import (
    LAYOUTS,
    MAX_BULLETS_PER_SLIDE,
    deck_spec,
    paginate,
    slide,
)
from backend.tools.office.pptx import bullet as slide_bullet
from backend.tools.office.pptx import from_findings as deck_from_findings
from backend.tools.office.xlsx import (
    cell,
    columns_of,
    safe_sheet_name,
    sheet_from_grid,
    sheet_from_records,
    workbook_spec,
)

__all__ = [
    "LAYOUTS",
    "MAX_BULLETS_PER_SLIDE",
    "cell",
    "citation",
    "columns_of",
    "deck_from_findings",
    "deck_spec",
    "document_bullet",
    "document_from_findings",
    "document_spec",
    "paginate",
    "safe_sheet_name",
    "section",
    "sheet_from_grid",
    "sheet_from_records",
    "slide",
    "slide_bullet",
    "workbook_spec",
]
