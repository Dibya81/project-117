# Project 117 — Mobile Implementation Handoff & Operator Manual

**Date:** September 2026  
**Module:** Native Android Mobile Application (`apps/mobile`)  
**Package:** `com.project117.mobile`  
**Build Status:** ✅ `BUILD SUCCESSFUL` (100% passing tests)  
**APK Output:** `apps/mobile/app/build/outputs/apk/debug/app-debug.apk`

---

## 1. Executive Summary & Deliverables

The Project 117 Android Mobile Application is complete, fully functional, and ready for deployment and testing on physical Android devices.

Key accomplishments in this delivery:
1. **Zero-Failure Test Suite:** All 7 canonical unit tests pass with `testDebugUnitTest` (`tests="7" skipped="0" failures="0" errors="0"`).
2. **Deterministic Demo Mode:** Complete offline end-to-end industrial workflow implemented via `DemoBackend`. No external backend or internet connectivity is needed for on-device demonstration.
3. **Pluggable Production Boundary:** Fully wired `LiveBackend` utilizing Retrofit 2, Moshi, OkHttp, and bearer auth interceptors targeting the official backend API contract.
4. **Complete Offline Sync Architecture:** Room DB (`pending_actions`, `local_evidence`, `equipment_cache`, `work_order_cache`, `sop_cache`) with background `SyncManager` ensuring idempotent offline-first field operation.
5. **Role & Permission Model:** Strict enforcement between `TECHNICIAN` (inspections, reading capture, issue reporting) and `SUPERVISOR` (emergency shutdown approvals).
6. **Backend Integration Specification:** Complete contract documented in `docs/MOBILE_BACKEND_CONTRACT.md`.

---

## 2. Architecture: Demo Mode vs Live Mode Boundary

The application abstracts all data and network operations behind the [`FieldBackend`](file:///c:/Users/manas/OneDrive/Documents/dragonbiter/GitHub/project-117/apps/mobile/app/src/main/java/com/project117/mobile/domain/backend/FieldBackend.kt) interface:

- **`DemoBackend` (Default for Field Demonstration):**
  - Self-contained, stateful industrial equipment simulator.
  - Houses the canonical **Pump P-102** telemetry, active critical work order `WO-2026-0891`, standard procedure `SOP-MEC-042`, agent tasks, and pending approvals.
  - Deterministic assistant query responses matching industrial standards (ISO 10816).
- **`LiveBackend` (Production Target):**
  - Communicates directly with the Project 117 backend gateway via standard REST endpoints.
  - Uses dynamic base URL resolution loaded from `AppConfig` / DataStore.
  - Supports automatic token refresh and multi-part media uploads.
- **Switching Modes:**
  - In-app toggle on the **Server Configuration** screen (`/server_config`).
  - Operators can switch between Demo Mode and Live Mode at runtime without recompiling.

---

## 3. Canonical P-102 Demo Workflow

The application implements a continuous industrial maintenance loop that can be demonstrated end-to-end:

```
[Login Screen]
   │
   ├─► Log in as "technician" / pass
   ▼
[Home Dashboard]
   │
   ├─► Review Active Alerts: Pump P-102 (7.8 mm/s vibration warning)
   ▼
[Equipment Directory]
   │
   ├─► Select "Pump P-102" (or tap QR Scan to scan simulated tag "EQ-P102-VIB")
   ▼
[P-102 Telemetry View]
   │
   ├─► Observe 7.8 mm/s RMS vibration (exceeding ISO 10816 threshold of 4.5 mm/s)
   ├─► Observe Bearing Temp: 82.4°C
   ▼
[Assigned Work Order: WO-2026-0891]
   │
   ├─► Step 1: LOTO Verification (Completed)
   ├─► Step 2: High-frequency accelerometer verification (Requires evidence)
   ▼
[Standard Operating Procedure: SOP-MEC-042]
   │
   ├─► Review "Centrifugal Pump Bearing Inspection & Vibration Protocol"
   ▼
[Inspection & Photo Evidence Screen]
   │
   ├─► Record manual vibration reading (7.8 mm/s)
   ├─► Capture/attach camera evidence photo of outboard bearing casing
   ├─► Submit inspection (saved locally to Room DB & uploaded/queued)
   ▼
[Report Issue Screen]
   │
   ├─► File CRITICAL issue: "Outboard bearing vibration spike 7.8 mm/s"
   ▼
[AI Field Assistant]
   │
   ├─► Query: "What is the status of Pump P-102?" -> Telemetry 7.8 mm/s summary
   ├─► Query: "What SOP applies to this pump?" -> Refers to SOP-MEC-042
   ▼
[Supervisor Approvals Screen]
   │
   ├─► Log in as "supervisor" (or switch active user)
   ├─► Review pending request: "APP-042 — Emergency Shutdown Authorization"
   ├─► Approve shutdown -> Work order transitions to COMPLETED
   ▼
[Offline Queue & Sync Dashboard]
   │
   ├─► Inspect pending actions & synced local evidence
   └─► Trigger manual sync or retry
```

---

## 4. Mobile Build & Execution Instructions

From the root of the repository:

```powershell
# Change directory to apps/mobile
cd apps/mobile

# 1. Run all unit tests
.\gradlew.bat testDebugUnitTest

# Expected output:
# 7 tests completed, 0 failed
# BUILD SUCCESSFUL

# 2. Build the Debug APK
.\gradlew.bat assembleDebug

# Expected output:
# BUILD SUCCESSFUL in ~30s
```

**Final APK Location:**
```
apps/mobile/app/build/outputs/apk/debug/app-debug.apk
```

---

## 5. Physical Device Installation

To install the APK on an Android device with USB debugging enabled:

```powershell
# Verify ADB detects the device
adb devices

# Install APK to device
adb install -r apps/mobile/app/build/outputs/apk/debug/app-debug.apk
```

---

## 6. Physical Device Manual Testing Checklist

| Test Item | Action | Expected Behavior |
| :--- | :--- | :--- |
| **App Launch** | Open Project 117 from launcher | Industrial splash screen loads, navigates to Login |
| **Demo Mode Login** | Enter `technician` / any password | Authenticates into Technician dashboard with role tags |
| **Telemetry Inspection** | Tap Pump P-102 in Equipment list | Displays 7.8 mm/s RMS vibration highlighted in critical amber/red |
| **Camera / QR Scan** | Tap Scan QR tag button | Camera preview opens; scanning "EQ-P102-VIB" navigates directly to P-102 |
| **Work Order Steps** | Open `WO-2026-0891` | Shows step checklist with Step 1 completed, Step 2 pending |
| **SOP Viewer** | Open `SOP-MEC-042` | Displays markdown protocol with ISO 10816 limits |
| **Photo Capture** | Tap "Add Photo" on Inspection screen | Native camera captures bearing photo; preview displays with timestamp |
| **Issue Submission** | Submit Critical Issue for P-102 | Issue creates, references evidence doc, updates status |
| **AI Assistant** | Ask "What SOP applies to this pump?" | Returns SOP-MEC-042 recommendation |
| **Supervisor Login** | Log out, log in as `supervisor` | Approvals badge visible; approval actions unlocked |
| **Approval Flow** | Approve `APP-042` with notes | Approval status becomes APPROVED; WO-2026-0891 marks COMPLETED |
| **Offline Mode** | Enable Airplane Mode on phone | App remains responsive; actions queue into SQLite database |
| **Offline Sync** | Disable Airplane Mode, tap Sync | Pending queue flushes; items mark SYNCED |
| **Server Config** | Open Server Settings screen | Can edit IP/Port and toggle Demo Mode vs Live Mode |

---

## 7. Known Mobile-Only Limitations & Notes

1. **Hardware Camera in Emulators:** CameraX requires hardware camera or simulated camera configured in AVD. The app includes simulated photo fallbacks for environments without a camera.
2. **Text-to-Speech / Speech-to-Text:** Uses Android standard `TextToSpeech` and `RecognizerIntent`. Physical devices without Google Speech Services installed will operate via text input.
3. **Live Mode Connection:** Live Mode requires a running instance of the Project 117 backend reachable at the IP configured in the Server Settings screen. For local development, use the host PC IP (e.g. `http://192.168.x.x:8000/api/v1/`).
