"""Phase 4 smoke test — upload → ingest → hybrid search → grounded chat.

Requires the backend running (default http://127.0.0.1:8000) with
P117_EMBEDDING_MODEL and P117_REASONING_MODEL served by the local Ollama:

    make run
    uv run python ../scripts/smoke_phase4.py [base_url]

Steps: build a real multi-page PDF with PyMuPDF, upload + reindex it through
the Phase 3 pipeline, then POST /api/search and assert citations carry
document/page/heading metadata, and finally POST /api/chat?use_rag=true and
assert evidence is attached to the turn.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def request_json(path: str, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def main() -> None:
    import fitz  # PyMuPDF

    # 1. Build a real multi-page PDF with a text layer.
    pdf_path = "/tmp/p117_smoke_phase4.pdf"
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

    # 2. Upload + reindex (Phase 3 pipeline fills the hybrid index).
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
        f"filename=\"compressor-manual.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
    ).encode() + open(pdf_path, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    upload = request_json(
        "/api/documents/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    document_id = upload["documents"][0]["id"]
    print("uploaded:", document_id, upload["documents"][0]["filename"])

    started = time.time()
    reindex = request_json(f"/api/documents/{document_id}/reindex", data=b"")
    print(f"reindexed in {time.time() - started:.1f}s:", json.dumps(reindex))
    assert reindex["status"] == "indexed" and reindex["chunk_count"] > 0

    # 3. Hybrid search with citations.
    started = time.time()
    search = request_json(
        "/api/search",
        data=json.dumps({"query": "bearing inspection hours", "top_k": 3}).encode(),
        headers={"Content-Type": "application/json"},
    )
    print(f"searched in {time.time() - started:.2f}s:", json.dumps(search["mode"]))
    assert search["total"] > 0, "hybrid search found nothing"
    top = search["results"][0]
    citation = top["citation"]
    print(
        "top citation:",
        {
            "document_id": citation["document_id"],
            "page": citation["page"],
            "heading_path": citation["heading_path"],
            "block_type": citation["block_type"],
        },
    )
    assert citation["document_id"] == document_id, "citation must resolve to the uploaded UUID"
    assert "bearing" in top["text"].lower()

    # Scoped search must hit only that document.
    scoped = request_json(
        "/api/search",
        data=json.dumps(
            {"query": "bearing inspection", "top_k": 5, "document_ids": [document_id]}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert scoped["total"] > 0
    assert all(r["citation"]["document_id"] == document_id for r in scoped["results"])
    print("scoped search ok:", scoped["total"], "result(s)")

    # 4. Grounded chat.
    turn = request_json(
        "/api/chat",
        data=json.dumps(
            {"message": "How often must bearing inspection occur?", "use_rag": True}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    print("grounded answer:", turn["response"][:200].replace("\n", " "))
    assert turn["evidence"], "grounded chat must return evidence"
    print("evidence chunks:", len(turn["evidence"]))
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
