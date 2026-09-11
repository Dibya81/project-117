"""Deliverables (Phase 10).

The division of labour that makes generated files trustworthy:

* the model writes a **spec** (:mod:`backend.deliverables.spec`) - what the
  document says;
* a reviewed **generator** turns that spec into a file, inside the sandbox -
  how the document is built;
* :class:`ArtifactService` owns the **lifecycle** - digest, storage, row,
  verification status, and the refusal to serve anything that fails either.

No model-authored code is executed anywhere in that chain.
"""

from backend.deliverables.service import (
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_UNVERIFIED,
    STATUS_WARNING,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactService,
    ArtifactSpecInvalid,
    safe_filename,
)
from backend.deliverables.spec import (
    ArtifactSpec,
    Bullet,
    Citation,
    Section,
    Sheet,
    Slide,
    SpecError,
    parse_spec,
)

__all__ = [
    "STATUS_FAILED",
    "STATUS_PASSED",
    "STATUS_PENDING",
    "STATUS_UNVERIFIED",
    "STATUS_WARNING",
    "ArtifactError",
    "ArtifactIntegrityError",
    "ArtifactNotFound",
    "ArtifactService",
    "ArtifactSpec",
    "ArtifactSpecInvalid",
    "Bullet",
    "Citation",
    "Section",
    "Sheet",
    "Slide",
    "SpecError",
    "parse_spec",
    "safe_filename",
]
