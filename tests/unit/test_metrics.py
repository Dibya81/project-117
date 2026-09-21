from __future__ import annotations


def test_metrics_accumulate(client):
    client.get("/health")
    client.get("/api/documents")
    snapshot = client.get("/api/metrics").json()

    # The metrics endpoint snapshots before its own request is counted by the
    # middleware, so health + documents are guaranteed visible.
    assert snapshot["counters"]["http.requests_total"] >= 2
    assert snapshot["counters"]["http.status.200"] >= 2
    assert snapshot["durations"], "request durations must be recorded"


def test_404s_are_counted(client):
    client.get("/api/documents/does-not-exist")
    snapshot = client.get("/api/metrics").json()
    assert snapshot["counters"].get("http.status.404", 0) >= 1
