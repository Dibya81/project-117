"""Phase 3 smoke test — upload → ingest → verify LanceDB citation metadata.

Requires the backend running (default http://127.0.0.1:8000) with
P117_EMBEDDING_MODEL served by the local Ollama. Run from backend/ (relative
P117_ paths resolve against the server's cwd, which is backend/ for local
runs — pass explicit paths if your server uses different ones):

    uv run python ../scripts/smoke_phase3.py [base_url] [lancedb_dir] [table]

Steps: build a real multi-page PDF with PyMuPDF, upload it, reindex it
through the localGPT pipeline, then assert the document row is `indexed` and
every LanceDB chunk row carries page-level citation metadata.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
LANCEDB_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "data/lancedb")
TABLE = sys.argv[3] if len(sys.argv) > 3 else "p117_chunks"


def request_json(path: str, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def main() -> None:
    import fitz  # PyMuPDF

    # 1. Build a real multi-page PDF with a text layer.
    pdf_path = Path("/tmp/p117_smoke.pdf")
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Compressor Maintenance Manual - Part {i + 1}")
        page.insert_text(
            (72, 120),
            f"Section {i + 1}: Bearing inspection every {500 + i * 250} hours. "
            "Record vibration readings and replace seals when wear exceeds specification.",
        )
    doc.save(pdf_path)
    doc.close()

    # 2. Upload.
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
        f"filename=\"compressor-manual.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    upload = request_json(
        "/api/documents/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    document_id = upload["documents"][0]["id"]
    print("uploaded:", document_id, upload["documents"][0]["filename"])

    # 3. Reindex through the real localGPT pipeline.
    started = time.time()
    result = request_json(f"/api/documents/{document_id}/reindex", data=b"")
    print(f"reindexed in {time.time() - started:.1f}s:", json.dumps(result))

    # 4. Verify document state.
    got = request_json(f"/api/documents/{document_id}")
    ingestion = got["metadata"]["ingestion"]
    print(
        "status:", got["status"],
        "| chunks:", ingestion["chunk_count"],
        "| embedder:", ingestion["embedding_model"],
        "| index_document_id:", ingestion["index_document_id"],
    )
    assert got["status"] == "indexed", got
    assert ingestion["chunk_count"] > 0

    # 5. Verify LanceDB rows carry citation metadata.
    import lancedb

    db = lancedb.connect(str(LANCEDB_DIR))
    table = db.open_table(TABLE)
    rows = table.to_arrow().select(["document_id", "chunk_index", "metadata"]).to_pylist()
    ours = [r for r in rows if r["document_id"].startswith(document_id)]
    print("lancedb rows for our document:", len(ours))
    assert ours, "no vectors found for the uploaded document"
    # localGPT's VectorIndexer stores the full chunk dict as JSON in the
    # `metadata` column: {chunk_id, text, metadata: {page, heading_path, ...}}
    # — citation fields live one level down.
    sample = json.loads(ours[0]["metadata"])
    inner = sample.get("metadata", sample)
    print(
        "sample citation metadata:",
        {k: inner.get(k) for k in ("page", "heading_path", "block_type", "chunk_index")},
    )
    assert all(
        "page" in (json.loads(r["metadata"]).get("metadata") or {}) for r in ours
    ), "page provenance missing"
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
