# Project 117 — Performance Baseline & Load Testing

## 1. Executive Summary

Project 117 is engineered for real-time responsiveness within an on-premise industrial plant control environment.

The system is sized for:
- **Concurrent Users:** 10–50 concurrent engineers, operators, and safety supervisors.
- **Latency Targets (p95):**
  - Read/Health endpoints (`/health`, `/api/equipment`, `/api/documents`): **< 50ms**
  - Complex analytical joins (`/api/materials/intelligence`): **< 150ms**
  - Edge model reasoning turns (`/api/chat/completions`, `RecoveryDecision`): **< 2.5s** (model hardware dependent)

---

## 2. Load Testing with Locust

The repository includes a load testing scenario modeled on actual plant traffic ratios in `tests/load/locustfile.py`.

### Running the Load Test
```bash
# Start backend server
uv run uvicorn backend.api.src.main:create_app --host 127.0.0.1 --port 8000 &

# Execute 30-second headless load test with 25 simulated operators
uv run locust -f tests/load/locustfile.py --headless -u 25 -r 5 -t 30s --host http://127.0.0.1:8000
```

---

## 3. Scale Envelope & Bottlenecks

### SQLite Single-Writer Ceiling
- Under WAL mode, read operations scale linearly across threads.
- Maximum sustainable transaction rate: **~3,500 write transactions/second** on standard NVMe SSDs.
- When write volume exceeds this envelope (e.g. continuous high-frequency IoT streaming > 10,000 writes/sec), telemetry must be buffered via in-memory ring buffers or routed to the PostgreSQL backend (Phase 17).

### Multi-Worker Scaling with Redis
- When deploying with multiple uvicorn workers (`P117_WORKERS > 1`), configure `P117_REDIS_URL=redis://localhost:6379/0` to enable the distributed token-bucket rate limiter.
- Multiple LLM replica instances can be load-balanced with `P117_LLM_EXTRA_URLS=http://host2:11434/v1,http://host3:11434/v1` to double or triple token generation throughput.
