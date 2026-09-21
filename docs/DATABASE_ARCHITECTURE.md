# Project 117 — Database Architecture & Consistency Model

## 1. Executive Summary

Project 117 implements a **domain-isolated, multi-database architecture** designed for sovereign, air-gapped on-premise industrial deployments.

By default, the platform uses 6 dedicated SQLite databases in WAL (Write-Ahead Logging) mode, providing complete operational isolation between concerns (simulation, operations, materials, security/audit, identity, and mobile field sync).

---

## 2. Database Roster & Domain Boundaries

| Database | Primary File | Core Tables / Records | Access Pattern |
|---|---|---|---|
| **Core & Knowledge** | `data/project117.db` | `documents`, `audit_events`, `workspaces`, `knowledge_entities` | High-frequency append for audit; batch writes for document indexing. |
| **Simulation Twin** | `data/simulation.db` | `plants`, `equipment`, `sensors`, `topology_edges`, `telemetry_history` | Read-heavy plant topology; periodic tick commits. |
| **Operations** | `data/operations.db` | `work_orders`, `approvals`, `incidents`, `actions` | Interactive user writes; high reliability state machine. |
| **Materials & Supply** | `data/materials.db` | `materials`, `inventory_balances`, `movements`, `production_series`, `suppliers`, `prices` | Analytical queries, deterministic calculations. |
| **Identity & Auth** | `data/identity.db` | `users`, `roles`, `credentials`, `enrollment_codes` | Authentication lookups; low write rate. |
| **Mobile Field Sync** | `data/mobile.db` | `sync_sessions`, `field_observations`, `offline_queue` | Batch synchronization from Android field tablets. |

---

## 3. Concurrency & Storage Engine

### WAL Mode & Busy Handlers
All SQLite connections are configured with:
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```
- **Read Concurrency:** Concurrent reader threads do not block writers, and writers do not block readers.
- **Single-Writer Safety:** SQLite enforces a single active writer per file. Under default single-worker (`P117_WORKERS=1`) deployment, SQLite handles thousands of operations per second with sub-millisecond latencies.

---

## 4. Cross-Database Consistency Model

Because domains are split across separate database files, cross-database operations do not use distributed transactions (2-Phase Commit / 2PC), avoiding distributed transaction coordinators and failure cascades.

### Transaction Sequencing Pattern
When a workflow spans multiple domains (e.g. creating a Work Order from an Incident requiring Material Spares reservation):

1. **Phase 1 (Verification):** Validate constraints across relevant domains (check material availability in `materials.db`, asset status in `simulation.db`).
2. **Phase 2 (Primary Write):** Commit the state transition in the authoritative domain (`operations.db`).
3. **Phase 3 (Side-Effect / Inventory Reservation):** Apply compensating/downstream adjustments (`materials.db`).
4. **Phase 4 (Audit Record):** Write tamper-evident audit row (`project117.db.audit_events`).

If a step fails after the primary write, the workflow registers an actionable compensating task in `operations.db` rather than leaving unrecorded state.

---

## 5. Migrations with Alembic

Database migrations are managed via **Alembic**:
```bash
# Check migration status
uv run alembic current

# Run migrations
uv run alembic upgrade head

# Generate a new migration
uv run alembic revision --autogenerate -m "add_column_name"
```

---

## 6. PostgreSQL Migration Path (Phase 17)

For enterprise deployments requiring multi-master clustering, cloud SaaS hosting, or high-concurrency writes across thousands of field technicians:

1. **Connection URL:** Switch `P117_DATABASE_URL` from `sqlite:///./data/project117.db` to `postgresql+psycopg://user:pass@host:5432/project117`.
2. **Schema Separation:** The 6 SQLite domains map directly to PostgreSQL schemas (`core`, `simulation`, `operations`, `materials`, `identity`, `mobile`) inside a single logical database or dedicated database clusters.
3. **ORM Compatibility:** All SQLAlchemy models in `backend.database.models` use standard portable ANSI SQL types (`String`, `BigInteger`, `DateTime`, `Text`, `Float`).
