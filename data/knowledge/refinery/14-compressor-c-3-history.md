---
doc_id: refinery-technical-knowledge-base
chunk: 14
section: Compressor C-3 History
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, compressor, C-3]
---
## 14. Compressor C-3 History

### 14.1 Identity

**C-3 (register twin C-1071), Recycle Gas Compressor.** Overlay asset from the U-200 console dataset; register counterpart C-1071, Reformer Recycle Compressor, area Catalytic Reforming, criticality Class 2 - high, manufacturer Helix Process, model Elliott 29M9-6, commissioned 2021-06-14. Register health 82/100, status WARNING. The mapping is exact in machine signature - see Section 4b.1.

### 14.2 Machine data

| Attribute | Value |
|---|---|
| Service | Recycle gas compression, U-200 hydrotreater train |
| Register tag | C-1071 |
| Overlay tag | C-3 |
| Kind | compressor |
| Running speed | 8,800 rpm (register nominal RPM-1071 = 8,840 rpm) |
| Vibration baseline | 5.7 mm/s at 8,800 rpm (learned, 2021-06-14) |
| 90-day rolling baseline | 5.80 mm/s (established 2026-09-07) |
| Alert threshold | 5.8 mm/s; alarm 7.1 mm/s (manual Table 7-2) |
| Latest survey | 6.8 mm/s RMS, 2026-09-06 (IR-204) |
| DE bearing temperature | 79 degC against a 68 degC baseline |
| Open work | WO-8852 (pending APR-231); WO-2417 alignment follow-up |

### 14.3 Instrumentation

Register instruments on C-1071:

| Sensor | Measurement | Unit | Nominal | Normal | Warning | Critical |
|---|---|---|---|---|---|---|
| PT-1071S | pressure | bar | 6.8 | 6.53 .. 7.07 | 6.12 .. 7.34 | 5.58 .. 7.89 |
| PT-1071D | pressure | bar | 19.5 | 18.72 .. 20.28 | 17.55 .. 21.06 | 15.99 .. 22.62 |
| VIB-1071 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| RPM-1071 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1071 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |

Overlay signals on C-3:

| Signal | Value | Unit | Baseline | Limit | Deviation | State |
|---|---|---|---|---|---|---|
| vibration_overall | 6.8 | mm/s | 5.8 | 7.1 | +18% | warning |
| bearing_temp_de | 79 | degC | 68 | 85 | +16% | warning |
| discharge_pressure | 42.1 | bar | 42 | 46 | +0% | normal |

### 14.4 Five-year chronology

| Date | Reference | Event |
|---|---|---|
| 2021-06-14 | Commissioning | Compression train recommissioned after the rotor re-installation campaign; baseline set at 5.7 mm/s at 8,800 rpm. |
| 2022-11-18 | A-19 / ME-067 | First minor vibration event: 6.1 mm/s transient during a lube-oil temperature excursion, cleared by oil flush and filter change. |
| 2022-06-14 | WO-2417 | Coupling alignment inspection raised (legacy CMMS number). |
| 2025-03-16 | IR-198 / ME-198 / WO-6120 | Drive-end bearing replaced. Outer-race spalling on two rolling elements, lube-oil varnish on the cage. Post-repair vibration 5.4 mm/s, re-baselined at 5.69 mm/s. |
| 2025-11-02 | ME-212 / WO-2417 | Hot alignment check. Coupling offset 0.06 mm against 0.10 mm tolerance; no correction required. |
| 2026-03-16 | Baseline | 90-day rolling mean 5.74 mm/s; trend classified as slow bearing degradation, quarterly review. |
| 2026-09-06 | IR-204 / A-51 | Survey measures 6.8 mm/s against a 5.8 mm/s rolling baseline (+18%), 1x dominant, DE bearing housing 79 degC against 68 degC. |
| 2026-09-07 | WO-8852 / APR-231 | Drive-end bearing inspection work order raised under SOP-07.3 rev4 section 4.3; outage approval pending. |

### 14.5 IR-204 spectral evidence

| Frequency | Amplitude (mm/s) | Interpretation |
|---|---|---|
| 1x running speed (49.6 Hz) | 4.9 | dominant; rising |
| 2x running speed | 1.1 | stable |
| Bearing defect band (BPFO) | 0.6 | slightly elevated |

Energy is concentrated at 1x running speed with a stable 2x component. Combined with the drive-end bearing temperature rise, this pattern is consistent with progressive drive-end bearing wear or a developing alignment shift, not with looseness or blade-pass excitation. On 2025-11-02 the coupling offset was 0.06 mm against a 0.10 mm tolerance, so alignment was eliminated as the primary driver at that time; the residual trend is therefore attributed to the bearing.

### 14.6 Register event history

| Date | Reference | Work order | Type | Scope |
|---|---|---|---|---|
| 2022-06-14 | ME-055 | WO-2417 | preventive | coupling alignment inspection raised (legacy CMMS number) |
| 2023-05-28 | IR-187 | - | inspection | Actuator overhauled, stroke re-profiled. |
| 2025-03-16 | ME-198 | WO-6120 | corrective | drive-end bearing replacement, OEM spare fitted, post-repair hot alignment |
| 2025-03-16 | IR-198 | - | inspection | Bearing replaced, alignment re-checked and accepted; returned to service. |
| 2025-11-02 | ME-232 | WO-2417 | preventive | hot alignment check, coupling offset 0.06 mm against 0.10 mm tolerance |
| 2025-12-02 | ME-237 | WO-6147 | corrective | rotor alignment check |
| 2026-02-10 | ME-247 | WO-8605 | preventive | lube-oil sampling and analysis |
| 2026-03-17 | ME-252 | WO-8610 | preventive | rotor alignment check |
| 2026-06-02 | ME-263 | WO-8621 | preventive | surge margin check |
| 2026-09-06 | IR-204 | - | inspection | Daily monitoring imposed, corrective work order WO-8852 raised, hot alignment check required before re-baselining. |
| 2026-09-07 | ME-280 | WO-8852 | corrective | drive-end bearing inspection raised from IR-204; pending approval |

### 14.7 Learned rules and standing controls

* **C-3 vibration baseline: 5.7 mm/s at 8,800 rpm.** This is the reference every deviation in the record is measured against.
* SOP-07.3 rev4 section 4.2: above 10% deviation, monitoring rises to once per shift and a corrective work order is raised within 72 hours.
* SOP-07.3 rev4 section 4.3: a drive-end bearing inspection is required when overall vibration exceeds baseline by 15% or more with 1x dominance, or when bearing housing temperature rises more than 10 degC above baseline. IR-204 satisfies both triggers.
* SOP-07.3 rev4 section 5: an outage on criticality-high equipment requires Maintenance Manager approval - this is APR-231.

### 14.8 Assessment

The machine is inside its alarm limit but outside the 10% deviation band and above the 15% bearing inspection trigger. The trend is progressive, not a step change. The correct posture is to keep the machine on line under once-per-shift monitoring while the outage window is approved, and to inspect the drive-end bearing at the first available opportunity rather than to wait for the alarm limit. If vibration reaches 7.1 mm/s, or bearing temperature reaches 85 degC, SOP-07.3 requires a load reduction and shift-supervisor notification.
