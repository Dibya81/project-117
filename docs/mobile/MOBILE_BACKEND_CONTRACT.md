# Project 117 — Mobile <-> Backend Integration Contract

**Document Version:** 1.0.0  
**Target Application:** Project 117 Native Android Application (`apps/mobile`)  
**Scope:** Strict interface specification between the Android Mobile APK and the Project 117 Backend / Main Manager.

---

## 1. Architectural Boundaries & System Principles

1. **Standalone Mobile Execution:** The Android application operates against an abstract interface (`FieldBackend`). It supports two operational modes:
   - **Demo Mode (`DemoBackend`):** Fully functional, local, zero-network deterministic simulator designed for offline inspection, field demos, and acceptance testing.
   - **Live Mode (`LiveBackend`):** Production client connecting via Retrofit/OkHttp to the real Project 117 backend.
2. **Dynamic Endpoint Configuration:** The mobile application does not hardcode backend URLs. Operators can configure the active server host, port, TLS setting, and toggle Demo vs Live mode directly from the in-app **Server Configuration Screen** or enrollment flow.
3. **No Direct Model/Database Access:** The mobile APK never communicates directly with cloud LLMs, PC/SCADA networks, or internal relational databases. All requests flow through the backend gateway. Chat queries to the industrial assistant are routed to `/chat`, where the backend handles AI agent orchestration.

---

## 2. Authentication & Session Protocol

### 2.1 Device Enrollment
Before first login, the physical Android device must be enrolled into the enterprise cluster.

- **Endpoint:** `POST /auth/enroll`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "device_id": "8f3b29c1-47a2-4a0b-bf38-091a134a6c8e",
    "enrollment_code": "ENROLL-2026-X9"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "enrolled": true,
    "device_token": "dtok_live_9941a8bc43f01"
  }
  ```

### 2.2 Operator Login
Authenticates field personnel and issues JWT session tokens with assigned roles and permission grants.

- **Endpoint:** `POST /auth/login`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "username": "technician",
    "password": "••••••••",
    "device_token": "dtok_live_9941a8bc43f01"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "reftok_81c9a12401f8",
    "user_id": "USR-001",
    "username": "technician",
    "display_name": "Field Technician Alex",
    "role": "TECHNICIAN",
    "permissions": [
      "view_equipment",
      "scan_qr",
      "execute_work_orders",
      "upload_evidence",
      "report_issue",
      "view_sop",
      "use_assistant"
    ]
  }
  ```
  *(Note: For Supervisor users, `role` is `"SUPERVISOR"` and `permissions` includes `"decide_approvals"`).*

### 2.3 Token Refresh
- **Endpoint:** `POST /auth/refresh`
- **Request Body:**
  ```json
  {
    "refresh_token": "reftok_81c9a12401f8"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### 2.4 Authenticated Identity
- **Endpoint:** `GET /auth/me`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (200 OK):** Same schema as `MeResponse` (user_id, username, display_name, role, permissions).

---

## 3. Telemetry & Equipment Operations

### 3.1 Equipment Inventory
- **Endpoint:** `GET /equipment`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "id": "EQ-P102",
        "name": "Pump P-102",
        "type": "Centrifugal Slurry Pump",
        "location": "Processing Plant - Unit 4B",
        "status": "DEGRADED",
        "qr_code": "EQ-P102-VIB",
        "barcode": "P102-883921",
        "manufacturer": "FlowServe Heavy Industries",
        "model": "Mark 3 Slurry 4x3-10",
        "serial_number": "FS-2021-9941A",
        "last_maintenance_date": "2026-06-15",
        "next_maintenance_date": "2026-09-15",
        "metadata": {
          "Rated RPM": "1780",
          "Impeller Dia": "280 mm",
          "Slurry Density": "1.35 kg/L",
          "Criticality": "Tier 1 (High Impact)"
        },
        "readings": [
          {
            "parameter": "Vibration Spectrum (RMS)",
            "value": "7.8",
            "unit": "mm/s",
            "timestamp": "Just now",
            "is_nominal": false
          },
          {
            "parameter": "Bearing Temperature",
            "value": "82.4",
            "unit": "°C",
            "timestamp": "Just now",
            "is_nominal": false
          }
        ]
      }
    ]
  }
  ```

### 3.2 Equipment Details
- **Endpoint:** `GET /equipment/{id}`
- **Response (200 OK):** Returns single `EquipmentDto`.

### 3.3 QR Identification
Identifies equipment when field operators scan physical QR tags or barcodes with the device camera.

- **Endpoint:** `POST /equipment/identify`
- **Request Body:**
  ```json
  {
    "qr_code": "EQ-P102-VIB"
  }
  ```
- **Response (200 OK):** Returns the identified `EquipmentDto`.
- **Response (404 Not Found):** If the QR tag is unknown.

---

## 4. Work Orders & Standard Operating Procedures (SOP)

### 4.1 Get Work Orders
- **Endpoint:** `GET /work-orders`
- **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "id": "WO-2026-0891",
        "title": "Emergency Outboard Bearing Inspection & Vibration Isolation",
        "description": "Continuous vibration spike detected on Pump P-102 exceeding ISO 10816 limit (7.8 mm/s). Perform immediate mechanical inspection and capture high-frequency accelerometer evidence.",
        "status": "IN_PROGRESS",
        "priority": "CRITICAL",
        "assigned_to": "Technician Alex",
        "equipment_id": "EQ-P102",
        "equipment_name": "Pump P-102",
        "due_date": "2026-09-15 18:00",
        "created_at": "2026-09-14 06:30",
        "updated_at": "Just now",
        "steps": [
          {
            "step_number": 1,
            "title": "Safety Lockout / Tagout (LOTO)",
            "description": "Verify local disconnect switch is locked and electrical tagout is confirmed.",
            "is_completed": true,
            "evidence_required": false,
            "evidence_ids": []
          },
          {
            "step_number": 2,
            "title": "Acoustic & Vibration Capture",
            "description": "Attach portable sensor probe to outboard bearing casing and record 10-second FFT snapshot.",
            "is_completed": false,
            "evidence_required": true,
            "evidence_ids": []
          }
        ],
        "issue_id": "ISSUE-P102-01",
        "notes": "Vibration levels consistently reading 7.8 mm/s."
      }
    ]
  }
  ```

### 4.2 Update Work Order Status
- **Endpoint:** `POST /work-orders/{id}/update`
- **Request Body:**
  ```json
  {
    "status": "COMPLETED",
    "notes": "Bearing inspection finished. Evidence attached."
  }
  ```

### 4.3 SOP / Knowledge Base
- **Endpoint:** `GET /knowledge/sop`
- **Endpoint:** `GET /knowledge/sop/{id}`
- **Response (200 OK) for `SOP-MEC-042`:**
  ```json
  {
    "id": "SOP-MEC-042",
    "title": "Centrifugal Pump Bearing Inspection & Vibration Protocol",
    "category": "Mechanical Maintenance",
    "version": "v3.2",
    "summary": "Mandatory standard protocol for inspecting heavy slurry pumps experiencing excessive mechanical vibration.",
    "content": "# SOP-MEC-042: Vibration Inspection Protocol\n\n## 1. Thresholds\n- Nominal: < 2.5 mm/s RMS\n- Warning: 2.5 - 4.5 mm/s RMS\n- Critical Alarm: > 4.5 mm/s RMS (ISO 10816)\n\n## 2. Immediate Action on Critical Reading\nIf vibration exceeds 7.0 mm/s (e.g. Pump P-102 reading 7.8 mm/s), halt continuous operation immediately and log an emergency shutdown approval request.",
    "equipment_types": ["Centrifugal Slurry Pump"],
    "tags": ["Vibration", "Bearing", "Emergency"],
    "last_updated": "2026-08-01"
  }
  ```

---

## 5. Field Evidence & Issue Reporting

### 5.1 Evidence Upload
Field photos, vibration logs, and diagnostic recordings are uploaded via standard multipart HTTP form data.

- **Endpoint:** `POST /documents/upload`
- **Headers:** `Content-Type: multipart/form-data`
- **Parts:**
  - `file`: Raw binary image/audio/document file.
  - `equipment_id`: (Optional string) e.g., `"EQ-P102"`
  - `work_order_id`: (Optional string) e.g., `"WO-2026-0891"`
  - `caption`: (Optional string) e.g., `"Bearing housing surface wear"`
- **Response (200 OK):**
  ```json
  {
    "document_id": "DOC-EVID-94819A01"
  }
  ```

### 5.2 Report Issue
- **Endpoint:** `POST /issues`
- **Request Body:**
  ```json
  {
    "equipment_id": "EQ-P102",
    "description": "Vibration spiking to 7.8 mm/s with excessive audible grinding noise.",
    "severity": "CRITICAL",
    "evidence_ids": ["DOC-EVID-94819A01"]
  }
  ```
- **Response (200 OK):** Returns created `IssueResponse`.

---

## 6. AI Field Assistant & Agent Tasks

### 6.1 Interactive Chat / Voice Assistant
- **Endpoint:** `POST /chat`
- **Headers:** `Authorization: Bearer <access_token>`
- **Request Body:**
  ```json
  {
    "message": "What is the status of Pump P-102?",
    "equipment_id": "EQ-P102",
    "work_order_id": "WO-2026-0891"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "response": "Pump P-102 (Centrifugal Slurry Pump) is in DEGRADED condition. Telemetry reports abnormal vibration at 7.8 mm/s (nominal 2.5 mm/s) and bearing temp at 82.4°C. Active work order WO-2026-0891 and Agent Task AT-0891 are assigned."
  }
  ```

### 6.2 Agent Tasks & Workflow Actions
Predictive AI models and supervisor workflows dispatch tasks to field technicians.

- **Endpoint:** `GET /agents/tasks`
- **Endpoint:** `POST /agents/tasks/{id}/acknowledge`
- **Endpoint:** `POST /agents/tasks/{id}/complete`
- **Complete Request Body:**
  ```json
  {
    "notes": "Vibration confirmed manually at 7.8 mm/s via portable probe.",
    "evidence_ids": ["DOC-EVID-94819A01"]
  }
  ```

### 6.3 Supervisor Approvals
- **Endpoint:** `GET /approvals`
- **Endpoint:** `POST /approvals/{id}/decide`
- **Request Body:**
  ```json
  {
    "decision": "approve",
    "notes": "Emergency shutdown authorized based on 7.8 mm/s reading and bearing photo."
  }
  ```

---

## 7. Offline Sync Queue Behavior

When connectivity is lost or spotty in remote plant units:
1. Actions (`report_issue`, `upload_evidence`, `update_work_order`, `complete_agent_task`, `decide_approval`) are safely stored in Room SQLite database table `pending_actions`.
2. Evidence files are cached locally in app internal storage and cataloged in `local_evidence`.
3. The background `SyncWorker` / `SyncManager` monitors network connectivity. Upon reconnection, actions are replayed idempotently in chronological order.
4. Upon successful sync of an evidence upload, the local database executes `updateSyncStatusByPath(localPath, "SYNCED", remoteId)` ensuring complete integrity between local storage and remote backend records.

---

## 8. Mobile Build & Validation Instructions

To verify or produce the Android APK:

```bash
# Navigate to mobile project directory
cd apps/mobile

# 1. Run all unit tests (must complete with 0 failures)
.\gradlew.bat testDebugUnitTest

# 2. Build the final Debug APK
.\gradlew.bat assembleDebug

# Output APK Location:
# apps/mobile/app/build/outputs/apk/debug/app-debug.apk
```
