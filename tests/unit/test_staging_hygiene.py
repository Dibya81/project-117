from pathlib import Path

import pytest
from backend.ingestion.staging import DocumentStager


def test_staged_context_cleans_up_on_success(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()

    file_path = uploads_dir / "test_doc.pdf"
    file_path.write_text("dummy content")

    stager = DocumentStager(staging_dir)
    doc_id = "doc-uuid-123"

    with stager.staged_context(doc_id, uploads_dir, "test_doc.pdf") as staged:
        assert staged.exists()
        assert staged.is_symlink()
        assert staged.name == f"{doc_id}.pdf"

    # After exiting context manager, symlink should be removed
    assert not staged.exists()


def test_staged_context_cleans_up_on_exception(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()

    file_path = uploads_dir / "crash_doc.pdf"
    file_path.write_text("crash content")

    stager = DocumentStager(staging_dir)
    doc_id = "doc-uuid-456"

    with pytest.raises(RuntimeError, match="Simulated crash"):
        with stager.staged_context(doc_id, uploads_dir, "crash_doc.pdf") as staged:
            assert staged.exists()
            raise RuntimeError("Simulated crash")

    # Even on exception, symlink must be unlinked
    assert not (staging_dir / f"{doc_id}.pdf").exists()
