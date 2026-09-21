from __future__ import annotations


def test_upload_and_delete_are_audited(client):
    upload = client.post(
        "/api/documents/upload",
        files={"files": ("audited.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    document_id = upload.json()["documents"][0]["id"]

    events = client.get("/api/audit", params={"action": "document.uploaded"}).json()
    assert events["total"] == 1
    event = events["events"][0]
    assert event["resource_type"] == "document"
    assert event["resource_id"] == document_id
    assert event["outcome"] == "success"
    assert event["detail"]["filename"] == "audited.pdf"

    # Fetch the same event by id.
    got = client.get(f"/api/audit/{event['id']}").json()
    assert got["id"] == event["id"]

    client.delete(f"/api/documents/{document_id}")
    deleted = client.get("/api/audit", params={"action": "document.deleted"}).json()
    assert deleted["total"] == 1

    # Unknown event -> 404.
    assert client.get("/api/audit/does-not-exist").status_code == 404


def test_audit_filters_by_resource(client):
    document_ids = []
    for name in ("one.pdf", "two.pdf"):
        upload = client.post(
            "/api/documents/upload",
            files={"files": (name, b"%PDF-1.4", "application/pdf")},
        )
        document_ids.append(upload.json()["documents"][0]["id"])

    # Two uploads => two document.uploaded events. The *unfiltered* audit log
    # is not asserted as a bare total: RequestAuditMiddleware additionally
    # writes one `http.post` request row per call, so two uploads legitimately
    # produce four rows. Counting them made this test fail once the middleware
    # landed, without anything being wrong.
    uploads = client.get("/api/audit", params={"action": "document.uploaded"}).json()
    assert uploads["total"] == 2

    # The filter this test is named for: by resource type.
    by_type = client.get("/api/audit", params={"resource_type": "document"}).json()
    assert by_type["total"] == 2
    assert {event["resource_type"] for event in by_type["events"]} == {"document"}

    # ...and by resource id, which must isolate exactly one document each.
    for document_id in document_ids:
        one = client.get("/api/audit", params={"resource_id": document_id}).json()
        assert one["total"] == 1
        event = one["events"][0]
        assert event["resource_id"] == document_id
        assert event["action"] == "document.uploaded"
        assert event["detail"]["filename"] in {"one.pdf", "two.pdf"}
