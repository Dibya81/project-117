"""Reading files a tool is allowed to see.

Two things make this more than a wrapper around ``open()``.

**A scope, not a path.** Every read resolves the requested path first and
*then* checks it against an explicit set of allowed roots. Resolving first
means ``../../etc/passwd`` and a symlink pointing out of the root are caught
by the same check, rather than by two separate string tests one of which will
eventually be forgotten.

**A byte budget.** A tool's output lands in a model's context window. Reads
are capped and truncation is reported, so a caller can tell a short file from
a trimmed one instead of quietly reasoning about half a document.

Binary document formats (PDF, DOCX, images) are deliberately *not* decoded
here. Extraction is :mod:`backend.ingestion`'s job, and a second extraction
path is exactly the duplicate implementation this repository has been pruning.
:func:`probe` reports what a file is; it does not pretend to read it.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.tools.base import ToolArgumentError

#: Hard ceiling on a single read. 2 MB of text is already far more than any
#: model can use in one turn; the point is to fail loudly rather than swap.
MAX_READ_BYTES = 2_000_000

#: Suffixes we will decode as text. Everything else is reported, not read.
TEXT_SUFFIXES = frozenset(
    {
        ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".ndjson",
        ".yaml", ".yml", ".log", ".ini", ".cfg", ".conf", ".toml", ".xml",
        ".html", ".htm", ".py", ".sql", ".sh", ".env",
    }
)

#: Suffixes that hold text but belong to the ingestion pipeline, not here.
DELEGATED_SUFFIXES = frozenset({".pdf", ".docx", ".doc", ".pptx", ".xlsx"})

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


class FileAccessDenied(ToolArgumentError):
    """The path resolved outside every allowed root."""

    reason = "file_access_denied"


class FileTooLarge(ToolArgumentError):
    reason = "file_too_large"


def _repo_root() -> Path:
    # backend/tools/files/reader.py -> repository root
    return Path(__file__).resolve().parents[3]


def _configured_roots() -> tuple[Path, ...]:
    raw = os.getenv("P117_FILE_ROOTS", "").strip()
    if raw:
        parts = [item.strip() for item in raw.replace(":", ",").split(",")]
        roots = tuple(Path(p).expanduser().resolve() for p in parts if p)
        if roots:
            return roots
    # Default: the repository's own data directory. Uploads, the demo dataset
    # and job workspaces all live under it, and nothing else does.
    return (( _repo_root() / "data").resolve(),)


@dataclass(frozen=True)
class FileScope:
    """The set of directories a tool call may read from."""

    roots: tuple[Path, ...]

    @classmethod
    def default(cls) -> "FileScope":
        return cls(roots=_configured_roots())

    def describe(self) -> list[str]:
        return [str(root) for root in self.roots]

    def resolve(self, candidate: str | Path) -> Path:
        """Resolve ``candidate`` and confirm it sits inside an allowed root.

        Relative paths are interpreted against the *first* root, which is the
        only interpretation that cannot be steered by the caller.
        """
        text = str(candidate or "").strip()
        if not text:
            raise ToolArgumentError("no path was supplied")
        if "\x00" in text:
            raise ToolArgumentError("path contains a null byte")
        raw = Path(text).expanduser()
        if not raw.is_absolute():
            raw = self.roots[0] / raw
        resolved = raw.resolve()
        for root in self.roots:
            if resolved == root or root in resolved.parents:
                return resolved
        raise FileAccessDenied(
            f"'{text}' resolves to {resolved}, which is outside the permitted "
            f"roots ({', '.join(self.describe())})"
        )

    def relative(self, path: Path) -> str:
        for root in self.roots:
            try:
                return str(path.relative_to(root))
            except ValueError:
                continue
        return str(path)


def default_scope() -> FileScope:
    return FileScope.default()


def _decode(data: bytes) -> tuple[str, str]:
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1/replace"


def probe(path: str | Path, *, scope: FileScope | None = None) -> dict[str, Any]:
    """Metadata for one file. Never reads its contents."""
    scope = scope or default_scope()
    resolved = scope.resolve(path)
    if not resolved.exists():
        raise ToolArgumentError(f"'{scope.relative(resolved)}' does not exist")
    stat = resolved.stat()
    suffix = resolved.suffix.lower()
    return {
        "path": scope.relative(resolved),
        "absolute": str(resolved),
        "kind": "directory" if resolved.is_dir() else "file",
        "suffix": suffix,
        "size_bytes": stat.st_size if resolved.is_file() else None,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(
            timespec="seconds"
        ),
        "readable_as_text": suffix in TEXT_SUFFIXES,
        "needs_ingestion": suffix in DELEGATED_SUFFIXES,
        "note": (
            "binary document format - ingest it and use search_documents/read_document "
            "rather than reading bytes here"
            if suffix in DELEGATED_SUFFIXES
            else ""
        ),
    }


def read_text(
    path: str | Path,
    *,
    scope: FileScope | None = None,
    max_bytes: int = MAX_READ_BYTES,
) -> dict[str, Any]:
    """Read a text file, capped and with the truncation stated."""
    scope = scope or default_scope()
    resolved = scope.resolve(path)
    if not resolved.is_file():
        raise ToolArgumentError(f"'{scope.relative(resolved)}' is not a file")
    suffix = resolved.suffix.lower()
    if suffix in DELEGATED_SUFFIXES:
        raise ToolArgumentError(
            f"'{scope.relative(resolved)}' is a {suffix} file; extraction belongs to "
            "the ingestion pipeline. Ingest it, then use read_document."
        )
    budget = max(1, min(int(max_bytes), MAX_READ_BYTES))
    size = resolved.stat().st_size
    with resolved.open("rb") as handle:
        data = handle.read(budget + 1)
    truncated = len(data) > budget
    if truncated:
        data = data[:budget]
    text, encoding = _decode(data)
    return {
        "path": scope.relative(resolved),
        "size_bytes": size,
        "bytes_read": len(data),
        "encoding": encoding,
        "truncated": truncated,
        "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "sha256": hashlib.sha256(data).hexdigest() if not truncated else None,
        "text": text,
    }


def read_records(
    path: str | Path,
    *,
    scope: FileScope | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Read a tabular/structured file into columns and rows.

    Supports ``.csv``, ``.tsv``, ``.json`` (array of objects) and ``.jsonl``.
    Anything else is refused by name rather than guessed at.
    """
    scope = scope or default_scope()
    resolved = scope.resolve(path)
    payload = read_text(resolved, scope=scope)
    suffix = resolved.suffix.lower()
    limit = max(1, min(int(limit), 5_000))

    if suffix in (".csv", ".tsv"):
        delimiter = "\t" if suffix == ".tsv" else ","
        reader = csv.DictReader(io.StringIO(payload["text"]), delimiter=delimiter)
        columns = list(reader.fieldnames or [])
        rows = [dict(row) for _, row in zip(range(limit), reader)]
    elif suffix in (".json",):
        try:
            parsed = json.loads(payload["text"] or "null")
        except ValueError as exc:
            raise ToolArgumentError(f"'{payload['path']}' is not valid JSON: {exc}") from exc
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ToolArgumentError(
                f"'{payload['path']}' holds a {type(parsed).__name__}; "
                "read_records expects an array of objects"
            )
        rows = [item for item in parsed[:limit] if isinstance(item, dict)]
        columns = _columns_of(rows)
    elif suffix in (".jsonl", ".ndjson"):
        rows = []
        for index, line in enumerate(payload["text"].splitlines()):
            if not line.strip():
                continue
            if len(rows) >= limit:
                break
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise ToolArgumentError(
                    f"'{payload['path']}' line {index + 1} is not valid JSON: {exc}"
                ) from exc
            if isinstance(item, dict):
                rows.append(item)
        columns = _columns_of(rows)
    else:
        raise ToolArgumentError(
            f"'{payload['path']}' has suffix '{suffix}'; read_records handles "
            ".csv, .tsv, .json and .jsonl"
        )

    return {
        "path": payload["path"],
        "format": suffix.lstrip("."),
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": payload["truncated"] or len(rows) >= limit,
    }


def _columns_of(rows: list[dict[str, Any]]) -> list[str]:
    """Union of keys in first-seen order - stable, and never loses a column."""
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(str(key))
    return seen


def list_dir(
    path: str | Path,
    *,
    scope: FileScope | None = None,
    pattern: str = "*",
    limit: int = 200,
) -> dict[str, Any]:
    """List one directory. Not recursive: a tool should ask for what it wants."""
    scope = scope or default_scope()
    resolved = scope.resolve(path)
    if not resolved.is_dir():
        raise ToolArgumentError(f"'{scope.relative(resolved)}' is not a directory")
    if pattern.startswith("/") or ".." in pattern:
        raise ToolArgumentError("pattern must be a simple glob, not a path")
    entries: list[dict[str, Any]] = []
    for child in sorted(resolved.glob(pattern)):
        if len(entries) >= max(1, min(int(limit), 1_000)):
            break
        try:
            stat = child.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": child.name,
                "path": scope.relative(child),
                "kind": "directory" if child.is_dir() else "file",
                "size_bytes": stat.st_size if child.is_file() else None,
                "suffix": child.suffix.lower(),
            }
        )
    return {
        "path": scope.relative(resolved),
        "pattern": pattern,
        "entries": entries,
        "count": len(entries),
    }


__all__ = [
    "DELEGATED_SUFFIXES",
    "MAX_READ_BYTES",
    "TEXT_SUFFIXES",
    "FileAccessDenied",
    "FileScope",
    "FileTooLarge",
    "default_scope",
    "list_dir",
    "probe",
    "read_records",
    "read_text",
]
