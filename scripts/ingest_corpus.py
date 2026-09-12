#!/usr/bin/env python3
"""Ingest the committed refinery corpus through the real document pipeline.

The corpus in `data/corpus/refinery/` is the project's document dataset: eight
genuine refinery artefacts (work order, incident report, inspection report, HSE
manual, SOP, two decks, an employee register). This script pushes them through
the same upload -> reindex path a user drives from the console, so what lands in
LanceDB is produced by the real converter rather than by a side channel.

It deliberately does not talk to the database directly: if ingestion is broken,
this script must fail the same way the product would.

Idempotent by default. The upload route always creates a new document row, so
running this script repeatedly used to leave four rows and four full sets of
vectors for each of the eight files — inflating the index and making retrieval
return the same passage several times. The script now converges the store to one
indexed row per corpus file: extra rows for a filename are deleted (which purges
their vectors), an already-indexed file is left alone, and only a missing or
failed file is (re)ingested. Pass --force to re-ingest everything regardless.

Usage (backend must be running):
    ./.venv/bin/python scripts/ingest_corpus.py [api-base] [corpus-dir] [--force]
"""

from __future__ import annotations

import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_args = [a for a in sys.argv[1:] if not a.startswith("--")]
FLAGS = {a for a in sys.argv[1:] if a.startswith("--")}
BASE = _args[0] if len(_args) > 0 else "http://127.0.0.1:8000"
CORPUS = Path(_args[1] if len(_args) > 1 else "data/corpus/refinery")
FORCE = "--force" in FLAGS

#: Files the pipeline is expected to convert. Anything else in the directory is
#: reported and skipped rather than silently ignored.
SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".html", ".htm"}


def _request(path: str, *, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:400]}


def list_documents() -> list[dict]:
    status, body = _request("/api/documents")
    if status != 200:
        return []
    return list(body.get("documents") or [])


def delete_document(document_id: str) -> bool:
    status, _ = _request(f"/api/documents/{document_id}", method="DELETE")
    return status in (200, 204)


def _post_json(path: str, payload: dict | None = None) -> tuple[int, dict]:
    return _request(path, method="POST", payload=payload)


def upload(path: Path) -> tuple[int, dict]:
    """Multipart POST to the upload route, one file per request."""
    boundary = f"----p117{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
            f'filename="{path.name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode(),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        f"{BASE}/api/documents/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:400]}


def main() -> int:
    if not CORPUS.is_dir():
        print(f"corpus directory not found: {CORPUS}")
        return 2

    files = sorted(p for p in CORPUS.iterdir() if p.is_file())
    if not files:
        print(f"no files in {CORPUS}")
        return 2

    # Fail fast and loudly if the backend is not up.
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=10) as r:
            if r.status != 200:
                print(f"backend unhealthy: HTTP {r.status}")
                return 2
    except Exception as exc:  # noqa: BLE001
        print(f"backend not reachable at {BASE}: {exc}")
        return 2

    print(f"corpus: {CORPUS}  ({len(files)} files)  ->  {BASE}{'  [--force]' if FORCE else ''}\n")

    existing = list_documents()
    by_name: dict[str, list[dict]] = {}
    for row in existing:
        by_name.setdefault(str(row.get("filename") or ""), []).append(row)

    indexed = skipped = failed = purged = 0
    total_chunks = 0

    for path in files:
        if path.suffix.lower() not in SUPPORTED:
            print(f"  SKIP    {path.name}  (unsupported extension)")
            skipped += 1
            continue

        rows = by_name.get(path.name, [])
        # Converge to at most one row per file. Prefer an already-indexed row so
        # a re-run is a no-op; delete the rest, which also purges their vectors.
        good = next((r for r in rows if r.get("status") == "indexed"), None)
        keep_id = None if FORCE else (good or {}).get("id")
        for row in rows:
            if row.get("id") == keep_id:
                continue
            if delete_document(str(row["id"])):
                purged += 1
                by_name[path.name] = [r for r in rows if r.get("id") == keep_id]
                print(f"  PURGE   {path.name}  removed duplicate row {str(row['id'])[:8]} ({row.get('status')})")

        if keep_id is not None:
            ing = ((good or {}).get("metadata") or {}).get("ingestion") or {}
            chunks = int(ing.get("chunk_count") or 0)
            total_chunks += chunks
            print(f"  CURRENT {path.name:<44} {chunks:>4} chunks (already indexed)")
            skipped += 1
            continue

        status, body = upload(path)
        docs = body.get("documents") or []
        if status not in (200, 201) or not docs:
            detail = body.get("error") or body.get("detail") or body.get("raw") or body
            print(f"  FAIL    {path.name}  upload HTTP {status}: {str(detail)[:160]}")
            failed += 1
            continue

        document_id = docs[0]["id"]
        started = time.perf_counter()
        status, body = _post_json(f"/api/documents/{document_id}/reindex")
        elapsed = time.perf_counter() - started

        if status != 200 or body.get("status") != "indexed":
            detail = body.get("error") or body.get("detail") or body
            print(f"  FAIL    {path.name}  index HTTP {status}: {str(detail)[:160]}")
            failed += 1
            continue

        chunks = int(body.get("chunk_count") or 0)
        total_chunks += chunks
        print(f"  INDEXED {path.name:<44} {chunks:>4} chunks in {elapsed:5.1f}s")
        indexed += 1

    print(
        f"\n{indexed} indexed, {skipped} current/skipped, {failed} failed, "
        f"{purged} duplicate row(s) purged  —  {total_chunks} chunks"
    )
    if len(files) and not FORCE:
        remaining = list_documents()
        names = {str(r.get("filename")) for r in remaining}
        corpus_names = {p.name for p in files if p.suffix.lower() in SUPPORTED}
        stray = names - corpus_names
        if stray:
            print(f"note: {len(stray)} document(s) in the store are not from this corpus: {sorted(stray)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
