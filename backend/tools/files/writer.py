"""Writing files on behalf of a job.

Writes are confined to a **per-job workspace** - ``<data>/workspace/<job_id>``
- created on demand. A job cannot write into the uploads directory, the demo
dataset, or another job's workspace, because the destination is derived from
the job id rather than accepted from the caller.

Overwriting is refused unless asked for explicitly. Silently replacing a file
that something else produced is the kind of thing that makes a demo
irreproducible for reasons nobody can reconstruct afterwards.

Every write returns the sha256 of the bytes that were written, so an artifact
record can point at exactly this content.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backend.tools.base import ToolArgumentError

#: Ceiling for one written file.
MAX_WRITE_BYTES = 8_000_000

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class WriteRefused(ToolArgumentError):
    reason = "write_refused"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def workspace_root() -> Path:
    """``P117_WORKSPACE_DIR`` if set, else ``<repo>/data/workspace``."""
    override = os.getenv("P117_WORKSPACE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (_repo_root() / "data" / "workspace").resolve()


def safe_name(name: str) -> str:
    """Reduce a caller-supplied name to a single safe filename.

    Directory components are dropped rather than sanitised: a tool that wants
    a subdirectory should say so through ``subdir``, where the value is
    checked, instead of smuggling one through a filename.
    """
    base = Path(str(name or "").strip()).name
    cleaned = _SAFE_NAME.sub("-", base).strip("-.")
    if not cleaned:
        raise ToolArgumentError(f"'{name}' does not contain a usable filename")
    return cleaned[:120]


def job_workspace(job_id: str | None, *, subdir: str = "") -> Path:
    """Return (creating if needed) the directory this job may write to."""
    token = safe_name(job_id or "adhoc")
    target = workspace_root() / token
    if subdir:
        piece = safe_name(subdir)
        target = target / piece
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_bytes(
    data: bytes,
    *,
    filename: str,
    job_id: str | None,
    subdir: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    if len(data) > MAX_WRITE_BYTES:
        raise WriteRefused(
            f"refusing to write {len(data)} bytes; the per-file limit is {MAX_WRITE_BYTES}"
        )
    directory = job_workspace(job_id, subdir=subdir)
    target = directory / safe_name(filename)
    if target.exists() and not overwrite:
        raise WriteRefused(
            f"'{target.name}' already exists in this workspace; pass overwrite=True "
            "to replace it deliberately"
        )
    tmp = target.with_name(target.name + ".partial")
    tmp.write_bytes(data)
    tmp.replace(target)
    return {
        "path": str(target),
        "filename": target.name,
        "workspace": str(directory),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "overwritten": bool(overwrite and target.exists()),
    }


def write_text(
    content: str,
    *,
    filename: str,
    job_id: str | None = None,
    subdir: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    if content is None:
        raise ToolArgumentError("no content was supplied")
    return _write_bytes(
        str(content).encode("utf-8"),
        filename=filename,
        job_id=job_id,
        subdir=subdir,
        overwrite=overwrite,
    )


def write_json(
    payload: Any,
    *,
    filename: str,
    job_id: str | None = None,
    subdir: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError) as exc:
        raise ToolArgumentError(f"payload is not JSON-serialisable: {exc}") from exc
    name = filename if str(filename).lower().endswith(".json") else f"{filename}.json"
    return write_text(
        text + "\n", filename=name, job_id=job_id, subdir=subdir, overwrite=overwrite
    )


def write_csv(
    rows: Iterable[Mapping[str, Any]] | Iterable[Sequence[Any]],
    *,
    filename: str,
    columns: Sequence[str] | None = None,
    job_id: str | None = None,
    subdir: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write records as CSV. Accepts dict rows or positional rows."""
    materialised = list(rows or [])
    buffer = io.StringIO()
    if materialised and isinstance(materialised[0], Mapping):
        header = list(columns or [])
        if not header:
            for row in materialised:
                for key in row:  # type: ignore[union-attr]
                    if key not in header:
                        header.append(str(key))
        writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in materialised:
            writer.writerow({key: row.get(key, "") for key in header})  # type: ignore[union-attr]
    else:
        writer = csv.writer(buffer)
        if columns:
            writer.writerow(list(columns))
        for row in materialised:
            writer.writerow(list(row))  # type: ignore[arg-type]
        header = list(columns or [])
    name = filename if str(filename).lower().endswith(".csv") else f"{filename}.csv"
    result = write_text(
        buffer.getvalue(), filename=name, job_id=job_id, subdir=subdir, overwrite=overwrite
    )
    result["row_count"] = len(materialised)
    result["columns"] = header
    return result


def list_outputs(job_id: str | None = None) -> dict[str, Any]:
    """What this job has written so far."""
    directory = job_workspace(job_id)
    entries = []
    for child in sorted(directory.rglob("*")):
        if child.is_file() and not child.name.endswith(".partial"):
            entries.append(
                {
                    "filename": child.name,
                    "path": str(child),
                    "size_bytes": child.stat().st_size,
                }
            )
    return {"workspace": str(directory), "files": entries, "count": len(entries)}


__all__ = [
    "MAX_WRITE_BYTES",
    "WriteRefused",
    "job_workspace",
    "list_outputs",
    "safe_name",
    "workspace_root",
    "write_csv",
    "write_json",
    "write_text",
]
