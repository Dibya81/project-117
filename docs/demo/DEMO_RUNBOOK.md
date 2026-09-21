# Project 117 — Demonstration Runbook

This runbook provides end-to-end instructions for demonstrating Project 117's sovereign on-premise industrial AI capabilities to stakeholders, security auditors, and industrial operators.

---

## 1. Prerequisites & Environment Check

Verify that the local environment is installed and configured without external internet dependencies:

```bash
# 1. Verify Python virtual environment and dependencies
uv sync

# 2. Run the integration test suite
uv run pytest tests/simulation/test_integration_pipeline.py -v

# 3. Verify Next.js console build
pnpm --filter @project-117/web build
```

---

## 2. Live Demos

### Demo 1: Sovereign Zero-Egress Network Enforcement
**Objective:** Prove that the application strictly operates on-premise, allowing local loopback services (Ollama, local databases) while intercepting and blocking external outbound data transfers.

```bash
uv run python scripts/demo/red_button_egress_test.py
```
- **Expected Outcome:** 
  - Local requests (`127.0.0.1:8000`, `localhost:11434`) are permitted.
  - Outbound calls to cloud endpoints (`api.openai.com`, external telemetry) are stopped by `EgressGuardTransport` with typed `EgressBlocked` exceptions.

---

### Demo 2: Ed25519 Cryptographic Signing & Tamper Detection
**Objective:** Demonstrate that generated industrial deliverables (incident reports, maintenance specs) are signed with an Ed25519 private key, and any post-generation file tampering is immediately detected and rejected.

```bash
uv run python scripts/demo/tamper_signature_demo.py
```
- **Expected Outcome:**
  - Artifact is generated and signed with a detached `.sig.json` sidecar.
  - Original file returns `SIGNATURE VALID`.
  - 1-byte simulated file modification returns `SIGNATURE INVALID` with digest mismatch detail.

---

### Demo 3: Cryptographic Audit Trail Hash-Chain Verification
**Objective:** Verify that every security event, role change, and incident trigger is appended to a tamper-evident SHA-256 Merkle/hash-chain in SQLite.

```bash
# Verify the active SQLite audit chain
uv run python scripts/verify_audit_chain.py data/project117.db
```
- **Expected Outcome:** `SUCCESS: Audit chain verified (<N> rows checked). Head hash: <hash>`

---

### Demo 4: Oil Refinery Simulation — Sensor Failure & 3-Agent Incident Workflow
**Objective:** Trigger a real sensor failure on the distillation column, watch the plant isolate the circuit, observe 3 autonomous agents collaborate, and generate a post-incident PDF report.

1. **Start Backend & Frontend:**
   ```bash
   # Terminal 1: Start FastAPI backend
   uv run uvicorn backend.main:app --port 8000 --reload

   # Terminal 2: Start Next.js console
   pnpm --filter @project-117/web dev
   ```

2. **Run the Sensor Disable Simulation via CLI or UI:**
   - **Via CLI:**
     ```bash
     bash scripts/demo/demo_disable_sensor.sh
     ```
   - **Via Web Console:**
     - Open `http://localhost:3000/simulation/live`
     - Click **"Disable Sensor"** on Pressure Transmitter `PT-101`
     - Observe:
       1. Sensor state transitions to `DISABLED`.
       2. Equipment `C-101` and related pipe circuit transitions to `ISOLATED` (Red highlight, flow stopped).
       3. Three real Ollama agents activate in sequence:
          - **Diagnostic Agent:** Identifies sensor drift vs hardware fault from telemetry.
          - **Operations Agent:** Generates emergency isolation and bypass procedure.
          - **Documentation Agent:** Retrieves exact refinery SOP citations via BM25/LanceDB.
       4. Click **"Download Post-Incident PDF Report"** to view Sections A–H with Ed25519 signature sidecar.

---

### Demo 5: Mobile SQLCipher Standalone Storage Verification
**Objective:** Prove field technician mobile storage uses AES-256-GCM SQLCipher encryption for offline access.

```bash
uv run python -c "
from backend.storage.mobile_sqlcipher import get_mobile_db
db = get_mobile_db('data/mobile_secure.db', passphrase='demo-field-key-2026')
print('Mobile SQLCipher storage initialized successfully.')
"
```

---

### Demo 6: OpenSandbox Container Network Namespace Inspection
**Objective:** Inspect spawned OpenSandbox execution containers live to prove `network_mode: none` and `cap_drop: ALL` are physically active in the Linux network namespace.

```bash
bash scripts/demo/demo_inspect_sandbox_namespace.sh
```
- **Expected Outcome:**
  - If Docker is active: Shows only `lo` interface, confirms `ip addr` contains zero external routes, and verifies `curl` fails.
  - If Docker is inactive: Honest reporting that OpenSandbox is not running on this host with `SandboxUnavailable`.

---

### Demo 7: Zero-Dependency Standalone Artifact Verification
**Objective:** Prove that third parties and auditors can verify Ed25519 signed deliverables using standard Python `cryptography` without importing the Project 117 backend or having access to internal databases.

```bash
# Verify any signed artifact with its detached .sig.json
python scripts/verify_artifact_standalone.py data/reports/INC-00018_Report.pdf
```
- **Expected Outcome:** `OK: Verified INC-00018_Report.pdf (Ed25519 signature valid, digest matched)`

```
