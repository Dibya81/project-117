# Project 117 — Field Operations (Android)

**Sovereign Industrial Intelligence · FIELD OPERATIONS**

The native Android client for Project 117. It gives a technician or supervisor the
field-side half of the system: scan a tag, read live equipment state, work a job,
capture evidence, and raise decisions — on a handset, in a plant, often with no
network.

The application is a **native Kotlin / Jetpack Compose client**, not a web wrapper.
It is a standalone Gradle build and is deliberately **not** part of the pnpm
workspace: it consumes no Node package.

---

## Architecture

```
        Compose UI  (ui/screens · ui/components · ui/theme)
             │
             ▼
        ViewModels  (Hilt-injected, StateFlow)
             │
             ▼
        ┌──────────────────────────────────────────────┐
        │  FieldBackend          domain/backend        │
        │  the ONLY data surface the UI may use        │
        └──────────────────────────────────────────────┘
             │                              │
             ▼                              ▼
      DemoBackend                     LiveBackend
   (in-process, offline)        (Project 117 API over HTTP)
             │                              │
             │                              ▼
             │                    Project117Api (Retrofit)
             │                    AuthInterceptor · DTOs
             ▼
        Room (AppDatabase)  ◄──  SyncManager / SyncWorker
        local queue + cache         (WorkManager)
```

**`DynamicFieldBackend`** implements `FieldBackend` and routes every call:

| `AppMode` | Delegate | Transport |
|---|---|---|
| `DEMO` | `DemoBackend` | none — entirely in-process |
| `LOCAL` | `LiveBackend` | cleartext HTTP to a host on your LAN |
| `PRODUCTION` | `LiveBackend` | HTTPS |

`LOCAL` and `PRODUCTION` are both **live** modes (`AppMode.isLive`). There is
**no silent fallback from a live mode to `DEMO`**: an unreachable server is
reported as offline and the work is queued, never quietly answered from demo
data. A technician must never be shown invented plant state.

**Screens never call Retrofit.** All data access goes through `FieldBackend`.

### Layers

| Package | Responsibility |
|---|---|
| `ui/theme` | Palette, typography, shapes. Industrial dark; one restrained accent. |
| `ui/components` | Shared components — status chips, cards, buttons, dialogs. Single source of visual truth. |
| `ui/screens` | 17 screens |
| `ui/navigation` | `NavRoutes` + `Project117NavGraph` |
| `ui/camera` | CameraX capture and ML Kit barcode scanning |
| `domain/model` | `AppMode`, `UserRole`, `Permissions`, and the domain models |
| `domain/backend` | `FieldBackend` — the abstraction |
| `data/backend` | `DemoBackend`, `LiveBackend`, `DynamicFieldBackend` |
| `data/remote` | Retrofit API, auth interceptor, DTOs |
| `data/local` | Room database, DAOs, entities, `SessionManager` |
| `data/sync` | `SyncManager` (queue, retry policy) and `SyncWorker` (background) |
| `di` | Hilt modules — network, database, backend binding |

---

## Branding

The application uses the **official Project 117 identity**: the silver-on-black
`117` monogram (a broken ring around the numerals, with the wireless glyph set
inside the `7`) above the `PROJECT 117` / `FIELD OPERATIONS` wordmark.

| Asset | Path | Use |
|---|---|---|
| Adaptive foreground | `mipmap-*/ic_launcher_foreground.png` | The mark alone, centred in the 108dp canvas' inner 72dp safe zone |
| Adaptive background | `drawable/ic_launcher_background.xml` | Flat `#000000` field, matching the logo |
| Adaptive monochrome | `mipmap-*/ic_launcher_monochrome.png` | Android 13+ themed-icon silhouette |
| Legacy square / round | `mipmap-*/ic_launcher{,_round}.png` | Full lockup, rounded-square and circular masks |
| In-app lockup | `drawable-nodpi/ic_project117_logo.png` | Login screen |

Two deliberate decisions:

- **The adaptive icon carries the mark only, not the wordmark.** Android masks
  adaptive icons aggressively (circle, squircle, teardrop) and the wordmark would
  be clipped on many launchers. The full lockup is used for the legacy icons and
  in-app, where it has room and the size to be legible.
- **The UI accent is not the logo's silver.** The mark is monochrome, which is
  unreadable as an interactive accent colour on a dark surface. The interface
  keeps a restrained blue (`#5B9BD8`) for controls and state, and the identity is
  carried by the logo artwork.

Do not redraw the mark. If brand artwork is updated, replace the PNGs from the
official source rather than tracing new geometry.

## Android Requirements

| | |
|---|---|
| **JDK** | 17 or 21. **Do not use JDK 25** — Gradle 8.9 and AGP 8.5.2 reject it. |
| **Gradle** | 8.9 (via the committed wrapper) |
| **Android Gradle Plugin** | 8.5.2 |
| **Kotlin** | 2.0.21 |
| **compileSdk / targetSdk** | 35 |
| **minSdk** | 26 (Android 8.0) |
| **Android SDK** | `platforms;android-35`, `build-tools;35.0.0`, `platform-tools` |
| **Device** | A physical handset is strongly preferred — the camera, QR scanning and Bluetooth-free LAN networking all need real hardware. An emulator works for everything except reachability of your own LAN host (use `10.0.2.2` there). |

Point Gradle at your JDK 21 if it is not your default:

```bash
# ~/.gradle/gradle.properties  (machine-local, not in the repository)
org.gradle.java.home=/path/to/jdk-21
```

Create `apps/mobile/local.properties` (gitignored) with your SDK path:

```properties
sdk.dir=/Users/you/android-sdk
```

---

## Setup

```bash
cd apps/mobile

# 1. Point at your Android SDK (gitignored)
echo "sdk.dir=$HOME/android-sdk" > local.properties

# 2. (Optional) point LOCAL at your development machine
#    See "Backend environments" below — or use the Server Configuration screen.
echo "P117_LOCAL_BACKEND_URL=http://192.168.1.25:8000/api/v1/" >> local.properties

# 3. Build
./gradlew assembleDebug
```

Install onto a connected handset:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

---

## Build and Test Commands

```bash
./gradlew testDebugUnitTest     # 7 unit tests
./gradlew assembleDebug         # debug APK
./gradlew assembleRelease       # release APK (see Limitations re: lintVitalRelease)
./gradlew lint                  # Android lint
./gradlew clean                 # remove build output
```

Unit test results are written to
`app/build/test-results/testDebugUnitTest/` and HTML to
`app/build/reports/tests/testDebugUnitTest/index.html`.

---

## Backend Environments

Three environments, selected on the **Server Configuration** screen. No machine's
IP address is committed anywhere in the repository.

| Environment | Backend | Default URL | Typical use |
|---|---|---|---|
| **DEMO** | `DemoBackend` | none | Offline demo; deterministic canonical data, no network at all |
| **LOCAL** | `LiveBackend` | `http://10.0.2.2:8000/api/v1/` | Your development machine over Wi-Fi |
| **PRODUCTION** | `LiveBackend` | `https://api.project117.com/api/v1/` | A real deployment |

### How the URL is resolved

1. The compiled-in default comes from `BuildConfig.LOCAL_BACKEND_URL` /
   `BuildConfig.PRODUCTION_BACKEND_URL`, which `app/build.gradle.kts` sets from,
   in order of precedence: `-P` Gradle property → `apps/mobile/local.properties`
   → the built-in default.
2. If the user saves a URL for an environment, that override is persisted **per
   environment** (`server_url_local`, `server_url_production`). Switching
   LOCAL → PRODUCTION → LOCAL restores the LAN address you typed.
3. "Use environment default" clears the override for the current environment.
4. Every URL is sanitised (trim, ensure a trailing `/`, normalise the path to end
   in `/api/v1/` exactly once — Retrofit requires this) and **validated**: the
   scheme must be `http`/`https` with a host; `LOCAL` must be `http`;
   `PRODUCTION` must be `https`. An invalid URL is refused with its reason shown
   verbatim.

### Overriding without touching the UI

```bash
./gradlew assembleDebug -PP117_LOCAL_BACKEND_URL=http://192.168.1.25:8000/api/v1/
```

or put the same key in `apps/mobile/local.properties` (gitignored).

---

## Connecting a Phone to Your Development Machine

Both devices must be on the **same Wi-Fi network**.

```bash
# 1. Backend listening on all interfaces (from the repository root)
.venv/bin/python -m uvicorn backend.api.src.main:create_app \
  --factory --host 0.0.0.0 --port 8000
```

```bash
# 2. Find your machine's LAN address
ipconfig getifaddr en0        # macOS Wi-Fi  → e.g. 192.168.1.25
```

```bash
# 3. macOS: allow incoming connections if the firewall prompts.
#    Android and the Mac must be on the same subnet (not a guest network).
```

```
        Mac  ── Wi-Fi ──►  192.168.1.25:8000
                                  ▲
        Android Phone ── Wi-Fi ───┘
```

4. On the handset: **Server Configuration → LOCAL →**
   `http://192.168.1.25:8000/api/v1/` **→ Test Connection**.
   Expect **Connected**. A failure shows the real reason.

**Android does not use `localhost` for your machine.** `localhost` on the phone is
the phone. Use the LAN IP, or `10.0.2.2` from an emulator.

If the phone cannot reach the host, check in this order: same subnet → host
firewall → backend bound to `0.0.0.0` rather than `127.0.0.1` → the port is not
being blocked by a VPN.

**Cleartext is a debug-only affordance.** `res/xml/network_security_config.xml`
denies cleartext by default and permits it only for `10.0.2.2`, `localhost` and
`127.0.0.1`. A debug-variant override (`src/debug/res/xml/`) relaxes this so a
sideloaded debug build can reach any LAN address. **Release builds never see that
override** and are HTTPS-only. Security is not disabled globally to make local
testing work.

---

## Offline Sync

Offline is not an error state — it is the normal state in a plant with poor
coverage.

- When `LiveBackend` returns `BackendResult.BackendOffline`, the work is written
  to **Room** and queued by `SyncManager` (`queueReportIssue`,
  `queueEvidenceUpload`).
- `SyncWorker` (WorkManager) retries in the background and drains the queue when
  connectivity returns. It is scheduled, not polled from the UI.
- `SyncStatusScreen` shows what is queued and offers a manual retry.
- The queue is **append-only from the UI's perspective**: nothing is discarded
  because the network was down.

`DemoBackend` needs none of this — it is entirely in-process.

---

## Permissions and Roles

`UserRole` — `TECHNICIAN`, `OPERATOR`, `SUPERVISOR`, `ADMIN`, `UNKNOWN`.

- `ADMIN` implicitly satisfies every permission (`UserSession.hasPermission`).
- `isSupervisorOrAbove` (`SUPERVISOR` or `ADMIN`) gates consequential actions.
- Fine-grained capabilities are string permissions (e.g. `equipment:view`,
  `work_orders:view`) carried on the session and checked with `hasPermission`.

**Supervisor approval** is a first-class flow: a consequential action raises an
approval, and `ApprovalsScreen` records an `ApprovalDecision`
(`APPROVE` / `REJECT`). The mobile client enforces the role; the backend remains
the authority.

---

## Canonical Demo Data

`DemoBackend` is deterministic and canonical, which is what makes the offline
demo reproducible:

| | |
|---|---|
| Equipment | **P-102** — with a deliberately abnormal vibration reading |
| Work order | The canonical job, with steps |
| SOP | **SOP-042** |
| Assistant | Fixed, deterministic responses (no model call) |

If Ollama is not running, or the backend is unreachable, `DEMO` still
demonstrates the entire field workflow end to end.

---

## Backend Contract

The mobile client's API contract is documented in
[`MOBILE_BACKEND_CONTRACT.md`](./MOBILE_BACKEND_CONTRACT.md), with the original
handoff notes in
[`MOBILE_IMPLEMENTATION_HANDOFF.md`](./MOBILE_IMPLEMENTATION_HANDOFF.md).

The contract is a **boundary**: the DTOs in `data/remote/dto/Dtos.kt` and the
Retrofit interface in `data/remote/api/Project117Api.kt` mirror it. Changing
either is a contract change and must be made on both sides.

**Do not add a second backend.** `FieldBackend` → `DemoBackend` / `LiveBackend`
is the only path. If a screen needs data the abstraction does not expose, add the
method to `FieldBackend` and implement it in both backends.

---

## Current Limitations

Stated plainly:

1. **`DemoBackend` is the offline source of truth; the live route needs the
   backend running.** `LOCAL` and `PRODUCTION` talk to the `/api/v1` mobile field
   API, which the backend now implements (24 endpoints, including a real login —
   see [`BACKEND_INTEGRATION_GAP.md`](./BACKEND_INTEGRATION_GAP.md) for the
   original gap and its resolution). If the server is unreachable the app shows
   offline and queues; if it is unreachable at *login* the app cannot sign in,
   which is the honest behaviour. The server-failure → recovery workflow inherits
   the backend's own limits (see the root README).

   **Sign in with a seeded SYNTHETIC DEMO account** (one per role), after
   enrolling the device — enrolment is a real gate:
   `technician` / `Demo-Technician-117!`, `operator` / `Demo-Operator-117!`,
   `supervisor` / `Demo-Supervisor-117!`, `admin` / `Demo-Admin-117!`.
   Enrolment codes: `ENROLL-2026-X9`, `ENROLL-2026-DEMO`, `ENROLL-2026-FIELD`.
2. **Release assembly is blocked by a pre-existing fatal lint error**
   (`RemoveWorkManagerInitializer`): the application implements
   `Configuration.Provider` while the manifest still declares the default
   `WorkManagerInitializer`. `assembleRelease` needs either a
   `tools:node="remove"` on that meta-data or `-x lintVitalRelease`. This was
   **not** fixed here because it changes WorkManager/sync initialisation.
3. **`HomeScreen` hardcodes `isOnline = true`** into the connection status bar, so
   the bar does not currently reflect a backend outage. `ServerConfigScreen` does
   report Connected / Offline / Failed correctly. Fixing the bar needs a health
   poll in the home ViewModel — a network/behaviour change, not a configuration
   one.
4. **`ServerConfigScreen` was not restyled** with the newer shared components, so
   it looks slightly less consistent than the other screens.
5. **Legacy preference migration**: the old single `server_url` key is
   deliberately not migrated (it may hold a removed hardcoded address), so an
   existing install re-enters its LAN URL once. A persisted `"LIVE"` mode is
   mapped to `LOCAL`, never demoted to `DEMO`.
6. **No instrumented (on-device) tests yet** — the 7 tests are JVM unit tests.
   Camera, LAN reachability and Compose rendering are not covered by an automated
   test.
7. **Typography uses platform fonts** (`FontFamily.Default` / `Monospace`). No
   font files are bundled.

---

## Related

- Root [`README.md`](../../README.md) — the whole system
- [`docs/FINAL_PROJECT_REPORT.md`](../FINAL_PROJECT_REPORT.md) — release audit
- [`docs/design/GLASS_SYSTEM.md`](../design/GLASS_SYSTEM.md) — the web console's design system
