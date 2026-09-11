"""File access helpers for tools.

Three concerns, kept apart on purpose: :mod:`reader` may only read inside an
explicit scope, :mod:`writer` may only write inside a job's own workspace,
and :mod:`converter` is pure and touches no filesystem at all.
"""

from __future__ import annotations

from backend.tools.files.converter import (
    FORMATS,
    convert,
    parse,
    parse_markdown_table,
    render,
)
from backend.tools.files.reader import (
    DELEGATED_SUFFIXES,
    MAX_READ_BYTES,
    TEXT_SUFFIXES,
    FileAccessDenied,
    FileScope,
    default_scope,
    list_dir,
    probe,
    read_records,
    read_text,
)
from backend.tools.files.writer import (
    MAX_WRITE_BYTES,
    WriteRefused,
    job_workspace,
    list_outputs,
    safe_name,
    workspace_root,
    write_csv,
    write_json,
    write_text,
)

__all__ = [
    "DELEGATED_SUFFIXES",
    "FORMATS",
    "MAX_READ_BYTES",
    "MAX_WRITE_BYTES",
    "TEXT_SUFFIXES",
    "FileAccessDenied",
    "FileScope",
    "WriteRefused",
    "convert",
    "default_scope",
    "job_workspace",
    "list_dir",
    "list_outputs",
    "parse",
    "parse_markdown_table",
    "probe",
    "read_records",
    "read_text",
    "render",
    "safe_name",
    "workspace_root",
    "write_csv",
    "write_json",
    "write_text",
]
