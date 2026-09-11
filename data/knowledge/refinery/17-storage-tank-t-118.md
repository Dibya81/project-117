---
doc_id: refinery-technical-knowledge-base
chunk: 17
section: Storage Tank T-118
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, tank, T-118]
---
## 17. Storage Tank T-118

### 17.1 Identity

**T-118 (register twin TK-1121), Intermediate Storage Tank.** Atmospheric storage tank in the tank farm; register counterpart TK-1121, Naphtha Tank, area Product Storage, criticality Class 2 - high, manufacturer Atlas Pumps, model BHEL FRT-118, commissioned 2021-07-01. Register health 89/100, status NORMAL.

### 17.2 Service and instrumentation

T-118 buffers intermediate product between the process units and the finished product tanks. It is instrumented for level (LT-1121, nominal 62%) and temperature (TT-1121, nominal 41 degC). The overlay reports level at 54% against a 55% baseline and a 90% limit, i.e. normal, and the asset is recorded healthy.

| Sensor | Measurement | Unit | Nominal | Normal | Warning | Critical |
|---|---|---|---|---|---|---|
| LT-1121 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1121 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |

Overlay signal:

| Signal | Value | Unit | Baseline | Limit | Deviation | State |
|---|---|---|---|---|---|---|
| level | 54 | % | 55 | 90 | -2% | normal |

### 17.3 Integrity and inspection regime

The tank is on a six-monthly external visual inspection cycle; the most recent was completed on 2026-08-18 under WO-8802 with no findings. The register twin's commissioned date is 2021-07-01 and its last recorded inspection was 2026-02-15. Tank integrity is a static problem: there is no vibration, no rotating degradation and no fouling mechanism in the failure-mode set that applies to it. The credible issues are level instrument error, roof seal wear, secondary containment breach and, at the extreme, overfill.

### 17.4 Learned rules and standing controls

* WO-8802 (2026-08-18) is the six-monthly external visual inspection; completed with no findings.
* Level is the safety-critical measurement: high level is a containment risk and low level is a transfer risk. LT-1121 is calibrated at every second inspection.
* A tank with an uncalibrated level transmitter must not be used to close an inventory balance; the level is cross-checked against the gauging tape at each external inspection.

### 17.5 Register event history

| Date | Reference | Work order | Type | Scope |
|---|---|---|---|---|
| 2021-11-16 | ME-025 | WO-4124 | preventive | internal floating roof check |
| 2024-04-23 | ME-152 | WO-5716 | preventive | external visual inspection |
| 2024-07-23 | ME-165 | WO-5729 | corrective | internal floating roof check |
| 2025-05-13 | ME-207 | WO-6117 | preventive | roof seal inspection |
| 2026-08-18 | ME-274 | WO-8802 | preventive | six-monthly external visual inspection, no findings |

### 17.6 Assessment

No action. The tank is inside every band, the level is below its baseline rather than above it, and the last two external inspections produced no findings. The only standing requirement is the six-monthly cycle, which is next due on the register interval computed in Section 4.
