"""Artifact generation.

Two distinct layers live here, and keeping them apart matters:

* **Format renderers** - ``pdf_generator``, ``docx_generator``,
  ``pptx_generator``, ``xlsx_generator``. These are command-line scripts
  executed *inside the sandbox* by
  :meth:`backend.sandbox.service.SandboxService.render_artifact`. They import
  third-party document libraries, so they must never run in the API process.
* **Content builders** - ``report``, ``maintenance``, ``inspection``,
  ``analysis``. Pure functions that turn operational data into a validated
  :class:`~backend.deliverables.spec.ArtifactSpec` payload. No I/O, no
  third-party imports, fully unit-testable.

The pipeline is therefore: operational data -> content builder -> validated
spec -> sandboxed renderer -> stored artifact with a SHA-256 digest.
"""

from backend.deliverables.generators.analysis import build_analysis_report
from backend.deliverables.generators.inspection import build_inspection_summary
from backend.deliverables.generators.maintenance import (
    build_maintenance_recommendation,
)
from backend.deliverables.generators.report import (
    build_report_spec,
    citation,
    uncited_notice,
)

__all__ = [
    "build_analysis_report",
    "build_inspection_summary",
    "build_maintenance_recommendation",
    "build_report_spec",
    "citation",
    "uncited_notice",
]
