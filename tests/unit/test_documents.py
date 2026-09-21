from __future__ import annotations

from pathlib import Path

from backend.api.src.main import create_app
from backend.config import Settings
from fastapi.testclient import TestClient


def test_upload_list_get_delete_roundtrip(client, settings):
    upload = client.post(
        "/api/documents/upload",
        files={"files": ("manual.txt", b"compressor maintenance procedure", "text/plain")},
    )
    assert upload.status_code == 201
    document = upload.json()["documents"][0]
    assert document["filename"] == "manual.txt"
    assert document["status"] == "stored"
    assert document["size_bytes"] == len(b"compressor maintenance procedure")
    document_id = document["id"]

    # File bytes actually landed on disk.
    assert list(Path(settings.uploads_dir).iterdir()), "uploaded file must exist on disk"

    listing = client.get("/api/documents").json()
    assert listing["total"] == 1
    assert listing["documents"][0]["id"] == document_id

    got = client.get(f"/api/documents/{document_id}").json()
    assert got["id"] == document_id
    assert got["filename"] == "manual.txt"

    deleted = client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert list(Path(settings.uploads_dir).iterdir()) == [], "file must be removed on delete"


def test_multiple_uploads_in_one_request(client):
    files = [
        ("files", ("a.pdf", b"%PDF-1.4 fake", "application/pdf")),
        ("files", ("b.md", b"# heading", "text/markdown")),
    ]
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 201
    assert response.json()["uploaded"] == 2


def test_unsupported_extension_rejected(client):
    response = client.post(
        "/api/documents/upload",
        files={"files": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "bad_request"


def test_oversize_upload_rejected(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        uploads_dir=tmp_path / "up",
        max_upload_bytes=10,
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/documents/upload",
            files={"files": ("big.pdf", b"x" * 100, "application/pdf")},
        )
    assert response.status_code == 413


def test_missing_document_returns_404(client):
    assert client.get("/api/documents/does-not-exist").status_code == 404
    assert client.delete("/api/documents/does-not-exist").status_code == 404


def test_list_documents_pagination_and_clamping(client):
    # Upload 5 files
    for i in range(5):
        client.post(
            "/api/documents/upload",
            files={"files": (f"doc_{i}.txt", f"procedure {i}".encode(), "text/plain")},
        )

    # Default pagination
    res = client.get("/api/documents").json()
    assert res["total"] == 5
    assert res["limit"] == 50
    assert res["offset"] == 0
    assert len(res["documents"]) == 5

    # Explicit limit + offset
    res_paged = client.get("/api/documents?limit=2&offset=1").json()
    assert res_paged["total"] == 5
    assert res_paged["limit"] == 2
    assert res_paged["offset"] == 1
    assert len(res_paged["documents"]) == 2

    # Hard-cap clamping: limit > 500 clamped to 500, limit < 1 clamped to 1, offset < 0 clamped to 0
    res_clamped = client.get("/api/documents?limit=1000&offset=-5").json()
    assert res_clamped["limit"] == 500
    assert res_clamped["offset"] == 0
