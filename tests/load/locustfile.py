"""Locust load test suite for Project 117.

Simulates on-premise industrial plant operations load across 4 traffic tiers:
- Tier 1 (60% weight): Health and telemetry polling (/health, /api/models)
- Tier 2 (20% weight): Document search and knowledge listings (/api/documents, /api/equipment)
- Tier 3 (10% weight): Operational metrics and history (/api/metrics, /api/work-orders)
- Tier 4 (10% weight): Conversational chat & AI completion (/api/chat/completions)

Usage:
  uv run locust -f tests/load/locustfile.py --headless -u 25 -r 5 -t 30s --host http://localhost:8000
"""

from __future__ import annotations

from locust import HttpUser, between, task


class PlantOperatorUser(HttpUser):
    wait_time = between(0.2, 1.0)

    @task(6)
    def check_health_and_posture(self) -> None:
        """Baseline health check and model status."""
        self.client.get("/health", name="GET /health")
        self.client.get("/api/models", name="GET /api/models")

    @task(2)
    def query_equipment_and_documents(self) -> None:
        """Operator looking up equipment details or document lists."""
        self.client.get("/api/equipment?limit=50", name="GET /api/equipment")
        self.client.get("/api/documents?limit=20", name="GET /api/documents")

    @task(1)
    def fetch_metrics_and_work_orders(self) -> None:
        """Prometheus metrics scrape and work order listing."""
        self.client.get("/api/metrics", name="GET /api/metrics")
        self.client.get("/api/work-orders", name="GET /api/work-orders")

    @task(1)
    def chat_grounded_inquiry(self) -> None:
        """Interactive chat turn with document grounding."""
        payload = {
            "messages": [
                {"role": "user", "content": "What is the operating pressure limit for column C-101?"}
            ],
            "use_rag": False,
        }
        headers = {"Content-Type": "application/json"}
        self.client.post("/api/chat/completions", json=payload, headers=headers, name="POST /api/chat/completions")
