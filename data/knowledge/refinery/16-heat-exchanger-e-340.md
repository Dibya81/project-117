---
doc_id: refinery-technical-knowledge-base
chunk: 16
section: Heat Exchanger E-340
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, exchanger, E-340]
---
## 16. Heat Exchanger E-340

### 16.1 Identity

**E-340 (register twin E-1063), Feed/Effluent Heat Exchanger.** Shell-and-tube exchanger on the U-200 hydrotreater train; register counterpart E-1063, NHT Effluent Cooler, area Naphtha Hydrotreater, criticality Class 1 - highest consequence, manufacturer Flowdyne, model Alfa Laval ST-340, commissioned 2021-10-16. Register health 84/100, status NORMAL.

### 16.2 Service and instrumentation

The exchanger recovers heat from the hydrotreater effluent to the reactor feed. Its condition is read almost entirely from three points: inlet temperature TT-1063I (nominal 210 degC), outlet temperature TT-1063O (nominal 188 degC) and tube-side flow FT-1063 (nominal 88 m3/h). Duty is inferred from the temperature drop across the unit; fouling shows up first as a shrinking delta-T at constant flow, then as a rising shell-side delta-P.

| Sensor | Measurement | Unit | Nominal | Normal | Warning | Critical |
|---|---|---|---|---|---|---|
| TT-1063I | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1063O | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1063 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |

Overlay signal:

| Signal | Value | Unit | Baseline | Limit | Deviation | State |
|---|---|---|---|---|---|---|
| delta_p | 0.42 | bar | 0.4 | 0.75 | +5% | normal |

### 16.3 Fouling analysis

The overlay delta-P is 0.42 bar against a 0.40 bar baseline and a 0.75 bar limit, a deviation of +5% - inside the normal band, which is why the quarterly review (WO-8810) expects no action. The register-side trend over five quarters:

| Quarter | Shell-side delta-P (bar) | Clean reference (bar) | Deviation from clean |
|---|---|---|---|
| 2025-Q3 | 0.280 | 0.280 | 0.0% |
| 2025-Q4 | 0.315 | 0.280 | 12.5% |
| 2026-Q1 | 0.350 | 0.280 | 25.0% |
| 2026-Q2 | 0.385 | 0.280 | 37.5% |
| 2026-Q3 | 0.420 | 0.280 | 50.0% |

Fouling is progressive and slow. The mechanism models as `fouling` with magnitude 0.3: fouling factor rises and duty and outlet temperature sag. The engineering response is to trend, not to clean early: cleaning has a cost and a window, and cleaning a bundle at 5% over the clean reference recovers almost no duty.

### 16.4 Learned rules and standing controls

* WO-8810 (raised 2026-08-26) is the quarterly delta-P trend review; its expected outcome is no action, and the work order exists to make the absence of action an explicit, recorded decision.
* A cleaning decision requires the delta-P to approach the 0.75 bar limit or the outlet temperature to fall outside the normal band at constant inlet conditions.
* The exchanger is not a rotating machine and carries no vibration channel; fouling is its only credible degradation path, together with `pressure_surge` on the shell side (scenario `sc-pressure-surge` targets the atmospheric column, but the same mechanism applies to any shell-side inventory).

### 16.5 Register event history

| Date | Reference | Work order | Type | Scope |
|---|---|---|---|---|
| 2024-03-26 | ME-148 | WO-5712 | preventive | tube bundle eddy-current survey |
| 2024-10-29 | ME-179 | WO-5743 | corrective | shell-side flow verification |
| 2025-05-20 | IR-199 | - | inspection | Cleaning deferred to the next window; trend review quarterly. |
| 2025-08-05 | ME-219 | WO-6130 | preventive | delta-P trend review and cleaning assessment |
| 2025-10-28 | ME-231 | WO-6142 | preventive | shell-side flow verification |
| 2026-08-26 | ME-276 | WO-8810 | preventive | quarterly delta-P trend review, no action expected |

### 16.6 Assessment

The exchanger is healthy. Delta-P is 5% above the clean reference and the outlet temperature is inside the normal band. The correct posture is to keep the quarterly trend review, watch for the point at which the outlet temperature starts to sag at constant flow (that is the real duty-loss signal, earlier and more useful than delta-P), and hold the bundle for the next planned window rather than an unscheduled clean.
