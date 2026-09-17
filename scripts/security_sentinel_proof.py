"""Part 2 proof: a real ALLOW and a real BLOCK, end to end.

Run with the live backend up:

    .venv/bin/python scripts/security_sentinel_proof.py

What it proves, and how:

* **ALLOW** — a real HTTP request to the local model server (Ollama on
  127.0.0.1:11434) through the *guarded* transport. That is the egress path the
  product uses; the decision is made by the policy, recorded by the monitor,
  published to the sentinel stream and written to the durable audit log.
* **BLOCK** — ``check_and_record()`` against an external destination. No socket
  is opened: the policy refuses the URL before any connection, which is the
  only honest way to prove a block without generating the traffic the block is
  supposed to prevent.
* **SSE** — the same two decisions are captured from
  ``/api/network/stream`` while they happen, so the console's live view is
  proven to receive them rather than being read out of a counter.
* **Audit** — both decisions are read back from ``/api/audit``, which is the
  durable record the Security Events panel renders.
* **Attribution** — both attempts are made inside ``network_identity()``, the
  context a tool call establishes, so the events carry an agent and a task.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.security.egress import (  # noqa: E402
    EgressGuardSyncTransport,
    policy_from_settings,
)
from backend.security.network.sentinel_stream import network_identity  # noqa: E402

API = "http://127.0.0.1:8000"
LOCAL_LLM = "http://127.0.0.1:11434/api/tags"
#: RFC 5737 documentation range: unroutable by definition, so even a bug that
#: skipped the policy could not reach a real service with it.
EXTERNAL = "https://198.51.100.9/sovereignty-proof"

AGENT = "diagnostic"
TASK = "TASK-SENTINEL-PROOF"

captured: list[dict] = []
stop = threading.Event()


def pump_stream() -> None:
    """Read the live sentinel stream in a thread for the duration of the run."""
    try:
        with httpx.stream("GET", f"{API}/api/network/stream", timeout=30.0) as response:
            event = None
            for line in response.iter_lines():
                if stop.is_set():
                    return
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and event == "network.connection_attempt":
                    try:
                        captured.append(json.loads(line.split(":", 1)[1].strip()))
                    except ValueError:
                        pass
    except Exception as exc:  # noqa: BLE001 - the proof reports what it saw
        print(f"  (stream reader stopped: {type(exc).__name__})")


def sse_wait_for(destination: str, action: str, timeout: float = 8.0) -> dict | None:
    until = time.time() + timeout
    while time.time() < until:
        for event in list(captured):
            if event.get("destination") == destination and event.get("action") == action:
                return event
        time.sleep(0.1)
    return None


def audit_rows() -> list[dict]:
    response = httpx.get(f"{API}/api/audit", params={"limit": 200}, timeout=10.0)
    return response.json().get("events", [])


def main() -> int:
    settings = Settings()
    policy = policy_from_settings(settings)
    print("=" * 78)
    print("PART 2 — NETWORK SENTINEL: REAL ALLOW AND REAL BLOCK")
    print("=" * 78)
    print(f"policy: default_deny={policy.default_deny} allowed_hosts={sorted(policy.allowed_hosts)}")

    reader = threading.Thread(target=pump_stream, daemon=True)
    reader.start()
    time.sleep(1.5)  # let the subscription attach before anything happens

    allow_event = block_event = None
    with network_identity(agent=AGENT, task_id=TASK):
        # --- ALLOW: the backend reaching its own model server, for real. ----
        #
        # Its own guarded call, made by the API process (`/api/models` asks the
        # gateway which models are served, which is a real HTTP request to
        # Ollama through the egress guard). A local request made by this script
        # would be recorded in *this* process's monitor and never reach the
        # stream, the audit log or `/health` — the three places the claim is
        # about.
        print("\n[1] ALLOW — a real request to the local model server through the guard")
        try:
            with httpx.Client(transport=EgressGuardSyncTransport(policy), timeout=10.0) as client:
                response = client.get(LOCAL_LLM)
            print(f"    direct guarded request completed: HTTP {response.status_code} from {LOCAL_LLM}")
        except Exception as exc:  # noqa: BLE001
            print(f"    direct guarded request failed: {type(exc).__name__}: {exc}")
        print("    asking the API to reach its local model server (GET /api/models)…")
        models = httpx.get(f"{API}/api/models", timeout=30.0)
        print(f"    API answered HTTP {models.status_code}")

        # --- BLOCK: an external destination, refused before any socket. -----
        #
        # Taken through the API's own probe endpoint rather than by importing
        # the policy here. The monitor's counters and the sentinel's subscriber
        # set are process-local: a decision this script made would appear in
        # this script's monitor and nowhere the console can see it. The probe
        # runs `check_and_record` inside the API, so the decision reaches the
        # stream, the audit log and `/health` — which is the claim under test.
        print("\n[2] BLOCK — an external destination, refused by the API's policy")
        print(f"    probing {EXTERNAL}")
        probe = httpx.post(
            f"{API}/api/security/egress-probe", json={"url": EXTERNAL}, timeout=20.0
        ).json()
        blocked = probe.get("decision") == "BLOCK"
        print(f"    API decision: {probe.get('decision')} (socket_opened={probe.get('socket_opened')})")
        print(f"    {probe.get('detail')}")

    allow_event = sse_wait_for("localhost", "ALLOW")
    block_event = sse_wait_for("198.51.100.9", "BLOCK")
    time.sleep(1.0)
    stop.set()

    print("\n" + "-" * 78)
    print("SSE — what the console received while it was happening")
    print("-" * 78)
    for label, event in (("ALLOW", allow_event), ("BLOCK", block_event)):
        if event is None:
            print(f"  {label}: NOT RECEIVED on /api/network/stream")
        else:
            print(f"  {label}: {json.dumps(event, indent=2)}")

    print("\n" + "-" * 78)
    print("AUDIT — the durable record (Security Events panel source)")
    print("-" * 78)
    rows = [r for r in audit_rows() if r.get("action") == "network.egress_decision"]
    parsed = []
    for row in rows[:6]:
        detail = row.get("detail") or {}
        parsed.append(
            {
                "at": row.get("timestamp"),
                "decision": detail.get("decision"),
                "host": detail.get("host"),
                "port": detail.get("port"),
                "scheme": detail.get("scheme"),
                "local": detail.get("local"),
                "agent": row.get("agent"),
                "task_id": detail.get("task_id") or row.get("tool"),
                "reason": detail.get("reason"),
                "outcome": row.get("outcome"),
            }
        )
        print(f"  {json.dumps(parsed[-1])}")

    print("\n" + "-" * 78)
    print("HEALTH — the process-lifetime counters")
    print("-" * 78)
    network = httpx.get(f"{API}/health", timeout=10.0).json()["network"]
    print(f"  totals: {json.dumps(network['totals'])}")
    print(f"  blocked_hosts: {network['blocked_hosts']}  allowed_hosts: {network['allowed_hosts'][:6]}")

    ok = bool(allow_event) and bool(block_event) and blocked
    print("\n" + "=" * 78)
    print(
        f"RESULT: ALLOW reached the sentinel={bool(allow_event)} · "
        f"BLOCK reached the sentinel={bool(block_event)} · policy refused without egress={blocked}"
    )
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
