---
doc_id: refinery-technical-knowledge-base
chunk: 15
section: Pump P-1042 History
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, pump, P-1042]
---
## 15. Pump P-1042 History

### 15.1 Identity

**P-1042 (register and overlay), Crude Charge Pump.** The only asset whose tag string exists in both vocabularies - an **exact** mapping. Register area Crude Distillation, criticality Class 3 - standard, manufacturer Vulcan Industrial, model Sulzer MSD 8x10x15, commissioned 2021-07-01, register health 84/100, status WARNING. The overlay names the same machine the Feed Charge Pump.

### 15.2 Current condition

Discharge pressure is running at 18.5 bar against a 17.0 bar operating alert threshold and a 16.2 bar baseline, a deviation of +14%. The transmitter envelope for PT-1042A is wider than the operating limit: its normal band is 17.76 to 19.24 bar, its warning band 16.65 to 19.98 bar and its critical band 15.17 to 21.46 bar. The excursion is therefore an operating-limit breach, not an instrument-envelope breach, and the process limit is the number that governs the response.

### 15.3 Instrumentation

| Sensor | Measurement | Unit | Nominal | Normal | Warning | Critical |
|---|---|---|---|---|---|---|
| PT-1042A | pressure | bar | 18.5 | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| PT-1042B | pressure | bar | 18.5 | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| FT-1042 | flow | m³/h | 96 | 92.16 .. 99.84 | 86.4 .. 103.68 | 78.72 .. 111.36 |
| TT-1042 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1042 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1042 | current | A | 84 | 80.64 .. 87.36 | 75.6 .. 90.72 | 68.88 .. 97.44 |
| KW-1042 | power | kW | 410 | 393.6 .. 426.4 | 369 .. 442.8 | 336.2 .. 475.6 |

Overlay signal:

| Signal | Value | Unit | Baseline | Limit | Deviation | State |
|---|---|---|---|---|---|---|
| discharge_pressure | 18.5 | bar | 16.2 | 17 | +14% | exceeded |

The seven-instrument block carries a redundant pressure pair, PT-1042A and PT-1042B. That redundancy is what makes scenario `sc-sensor-failure` survivable: if PT-1042A fails, PT-1042B carries the process and SOP-14.2 governs the response without stopping the pump.

### 15.4 Exercises that target this pump

| Scenario | Name | Steps |
|---|---|---|
| sc-sensor-failure | PT-1042A sensor failure | inject_failure -> e-P-1042 (sensor_failure) |
| sc-cavitation | P-1042 pump cavitation | inject_failure -> e-P-1042 (cavitation) |
| sc-oil-leak | P-1042 seal failure — oil leak | inject_failure -> e-P-1042 (seal_leak) |
| sc-cascade | Cascading failure — charge pump trip | inject_failure -> e-P-1042 (trip) |
| sc-drift | PT-1042A instrument drift | inject_failure -> e-P-1042 (instrument_drift) |

### 15.5 Learned rules and standing controls

* **P-1042 discharge pressure alert threshold: 17 bar.** This is an operating limit, held separately from the PT-1042A transmitter envelope, because the transmitter is deliberately ranged wider than the process limit.
* SOP-14.2 rev6 governs field instrument failure: mark the transmitter unavailable, validate the alternate, cross-check against a correlated measurement (flow against pump discharge pressure), and move to attended operation if no consistent alternate exists.
* WO-8841 (raised 2026-09-04) is the open corrective work order: check the relief path and impeller wear.

### 15.6 Register event history

| Date | Reference | Work order | Type | Scope |
|---|---|---|---|---|
| 2021-11-02 | ME-023 | WO-4122 | corrective | coupling alignment check |
| 2022-06-07 | ME-054 | WO-4722 | corrective | coupling alignment check |
| 2025-09-02 | ME-223 | WO-6134 | preventive | suction strainer cleaning |
| 2026-02-03 | ME-246 | WO-8604 | corrective | mechanical seal inspection |
| 2026-05-19 | ME-261 | WO-8619 | preventive | mechanical seal inspection |
| 2026-06-30 | ME-267 | WO-8625 | preventive | bearing lubrication and vibration survey |
| 2026-09-04 | ME-279 | WO-8841 | corrective | discharge pressure investigation, relief path and impeller check |

### 15.7 Assessment

Two credible causes fit a +14% discharge pressure excursion with stable flow: impeller wear raising the head required for the same duty, or a downstream restriction raising the back pressure. The correct next step is to trend FT-1042 against PT-1042A and PT-1042B together - if flow is falling while pressure rises, the restriction is downstream; if flow and pressure rise together, the pump is being asked for more head. Suction conditions should be confirmed against the desalter and crude storage levels before any mechanical work is scheduled, because cavitation (scenario `sc-cavitation`) produces the same pressure signature.
