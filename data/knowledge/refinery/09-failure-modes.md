---
doc_id: refinery-technical-knowledge-base
chunk: 9
section: Failure Modes
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, failure]
---
## 9. Failure Modes

The simulation defines 12 failure modes. Each mode names the equipment kinds it applies to, the physical mechanism it models, and the magnitude of its effect on the affected measurements. The table below is the failure-mode register; the subsections give detection and response.

| Mode id | Name | Applies to | Mechanism | Magnitude | Exposed units | Recorded occurrences |
|---|---|---|---|---|---|---|
| sensor_failure | Sensor failure | pressure | sensor | 1 | 0 | 1 |
| instrument_drift | Instrument drift | temperature, pressure, flow | drift | 1 | 0 | 1 |
| bearing_wear | Bearing wear | pump, compressor, motor | degrade | 0.25 | 21 | 19 |
| cavitation | Pump cavitation | pump | degrade | 0.4 | 14 | 15 |
| bearing_overheat | Bearing overheating | pump, motor, compressor | drift | 1 | 21 | 23 |
| valve_stuck | Valve failure (stuck) | valve | degrade | 0.6 | 5 | 5 |
| seal_leak | Seal failure / oil leak | pump, vessel | leak | 0.45 | 24 | 17 |
| pressure_surge | Pressure surge | vessel, column, exchanger | surge | 0.35 | 18 | 15 |
| trip | Equipment trip | compressor, pump, motor | stop | 1 | 21 | 27 |
| fouling | Heat exchanger fouling | exchanger | degrade | 0.3 | 6 | 7 |
| overload | Motor overload | motor, conveyor | degrade | 0.5 | 1 | 2 |
| esd | Emergency shutdown | safety | stop | 1 | 2 | 2 |

### 9.1 Sensor failure

**Mode id:** `sensor_failure`. **Mechanism:** sensor. **Magnitude:** 1. **Applies to:** pressure.

Primary measurement element fails; quality goes BAD.

Exposed register units (0): .

**Response.** Mark the transmitter unavailable, validate an alternate, cross-check against a correlated measurement, and move the unit to attended operation if no consistent alternate exists (SOP-14.2 rev6).

Recorded occurrences in the review period: 1.

### 9.2 Instrument drift

**Mode id:** `instrument_drift`. **Mechanism:** drift. **Magnitude:** 1. **Applies to:** temperature, pressure, flow.

Transmitter reading drifts away from true value.

Exposed register units (0): .

**Response.** Freeze automatic action on the drifting point, raise a calibration work order, and replace the element if drift recurs within one month (SOP-14.7 rev3).

Recorded occurrences in the review period: 1.

### 9.3 Bearing wear

**Mode id:** `bearing_wear`. **Mechanism:** degrade. **Magnitude:** 0.25. **Applies to:** pump, compressor, motor.

Vibration signature rises; capacity degrades.

Exposed register units (21): P-1001, P-1002, P-1202, P-1042, P-1051, C-1053, P-1061, C-1071, C-1082, P-1084, P-1091, C-1125, P-1127, C-1112, P-1124, P-1131, P-1132, P-1142, M-1143, C-1152, P-1171.

**Response.** Increase monitoring frequency, raise a corrective work order, and inspect the bearing when overall vibration exceeds baseline by 15% with 1x dominance (SOP-07.3 rev4 section 4.3).

Recorded occurrences in the review period: 19.

### 9.4 Pump cavitation

**Mode id:** `cavitation`. **Mechanism:** degrade. **Magnitude:** 0.4. **Applies to:** pump.

Net positive suction head lost; flow and pressure become unstable.

Exposed register units (14): P-1001, P-1002, P-1202, P-1042, P-1051, P-1061, P-1084, P-1091, P-1127, P-1124, P-1131, P-1132, P-1142, P-1171.

**Response.** Reduce speed or throttle discharge, restore upstream inventory, and stop the pump if suction conditions cannot be restored promptly (SOP-22.4 rev2).

Recorded occurrences in the review period: 15.

### 9.5 Bearing overheating

**Mode id:** `bearing_overheat`. **Mechanism:** drift. **Magnitude:** 1. **Applies to:** pump, motor, compressor.

Bearing temperature climbs toward trip.

Exposed register units (21): P-1001, P-1002, P-1202, P-1042, P-1051, C-1053, P-1061, C-1071, C-1082, P-1084, P-1091, C-1125, P-1127, C-1112, P-1124, P-1131, P-1132, P-1142, M-1143, C-1152, P-1171.

**Response.** Reduce load, check lubrication and cooling, and stop on a controlled ramp if vibration leaves the critical envelope (SOP-22.1 rev5).

Recorded occurrences in the review period: 23.

### 9.6 Valve failure (stuck)

**Mode id:** `valve_stuck`. **Mechanism:** degrade. **Magnitude:** 0.6. **Applies to:** valve.

Valve stops responding; flow restricted.

Exposed register units (5): V-1003, V-1103, V-1203, V-1047, V-1064.

**Response.** Place the loop in manual, hold the last safe position, and establish whether the process can be controlled from an alternate path (SOP-52.4 rev2).

Recorded occurrences in the review period: 5.

### 9.7 Seal failure / oil leak

**Mode id:** `seal_leak`. **Mechanism:** leak. **Magnitude:** 0.45. **Applies to:** pump, vessel.

Mechanical seal failure; medium escapes, detectors trip.

Exposed register units (24): P-1001, P-1002, VS-1201, P-1202, P-1042, VS-1046, P-1051, P-1061, VS-1062, VS-1073, VS-1081, P-1084, P-1091, VS-1092, VS-1126, P-1127, VS-1113, P-1124, P-1131, P-1132, P-1142, VS-1162, P-1171, VS-1172.

**Response.** Treat as a real release, isolate and depressurise, establish the exclusion zone, and reset the detector only after the release is cleared (SOP-31.5 rev7, SOP-41.2 rev8).

Recorded occurrences in the review period: 17.

### 9.8 Pressure surge

**Mode id:** `pressure_surge`. **Mechanism:** surge. **Magnitude:** 0.35. **Applies to:** vessel, column, exchanger.

Upstream excursion drives pressures over envelope.

Exposed register units (18): E-1004, VS-1201, COL-1044, E-1045, VS-1046, COL-1052, E-1054, VS-1062, E-1063, VS-1073, VS-1081, E-1083, VS-1092, E-1093, VS-1126, VS-1113, VS-1162, VS-1172.

**Response.** Confirm against a second transmitter, reduce inlet flow, verify the relief path to flare, and check for a downstream restriction (SOP-27.9 rev3).

Recorded occurrences in the review period: 15.

### 9.9 Equipment trip

**Mode id:** `trip`. **Mechanism:** stop. **Magnitude:** 1. **Applies to:** compressor, pump, motor.

Machine trips offline; dependent flow collapses.

Exposed register units (21): P-1001, P-1002, P-1202, P-1042, P-1051, C-1053, P-1061, C-1071, C-1082, P-1084, P-1091, C-1125, P-1127, C-1112, P-1124, P-1131, P-1132, P-1142, M-1143, C-1152, P-1171.

**Response.** Do not reset without establishing the cause, start the spare where one exists, and inspect the coupling and driven shaft before restart (SOP-18.3 rev4).

Recorded occurrences in the review period: 27.

### 9.10 Heat exchanger fouling

**Mode id:** `fouling`. **Mechanism:** degrade. **Magnitude:** 0.3. **Applies to:** exchanger.

Fouling factor rises; duty and outlet temperature sag.

Exposed register units (6): E-1004, E-1045, E-1054, E-1063, E-1083, E-1093.

**Response.** Trend shell-side delta-P against the clean reference, clean at the next available window, and re-rate the duty until then.

Recorded occurrences in the review period: 7.

### 9.11 Motor overload

**Mode id:** `overload`. **Mechanism:** degrade. **Magnitude:** 0.5. **Applies to:** motor, conveyor.

Current draw exceeds rated; thermal protection near.

Exposed register units (1): M-1143.

**Response.** Do not reset and restart a tripped drive; check the driven equipment's discharge conditions before assuming a motor fault (SOP-18.3 rev4).

Recorded occurrences in the review period: 2.

### 9.12 Emergency shutdown

**Mode id:** `esd`. **Mechanism:** stop. **Magnitude:** 1. **Applies to:** safety.

Safety system initiates a controlled area shutdown.

Exposed register units (2): ESD-1181, ESD-1182.

**Response.** Execute the area shutdown per the unit procedure and reset only after the initiating condition is cleared and the area is confirmed safe.

Recorded occurrences in the review period: 2.

### 9.13 Detection summary

Each failure mode has a primary measurement and a corroborating channel. The corroborating channel is what prevents a single failed transmitter from being mistaken for a process event, and it is the reason the pump blocks carry a redundant pressure pair.

| Mode id | Name | Primary measurement | Corroborating channel | Reference |
|---|---|---|---|---|
| sensor_failure | Sensor failure | pressure | redundant pressure pair (A/B) on the same block | SOP-14.2 rev6 |
| instrument_drift | Instrument drift | temperature / pressure / flow | correlated measurement on the same service | SOP-14.7 rev3 |
| bearing_wear | Bearing wear | vibration | overall vibration against the learned baseline | SOP-07.3 rev4 s.4.3 |
| cavitation | Pump cavitation | flow / pressure | suction pressure and upstream level | SOP-22.4 rev2 |
| bearing_overheat | Bearing overheating | temperature | bearing-housing thermocouple or RTD | SOP-22.1 rev5 |
| valve_stuck | Valve failure (stuck) | position | commanded vs actual position feedback | SOP-52.4 rev2 |
| seal_leak | Seal failure / oil leak | leak / gas | latched area detector | SOP-31.5 rev7 |
| pressure_surge | Pressure surge | pressure | second independent transmitter | SOP-27.9 rev3 |
| trip | Equipment trip | current | current signature and drive status | SOP-18.3 rev4 |
| fouling | Heat exchanger fouling | temperature / flow | delta-T and delta-P at constant flow | fouling trend review |
| overload | Motor overload | current | current draw against the rated envelope | SOP-18.3 rev4 |
| esd | Emergency shutdown | gas / leak | fire and gas panel matrix | SOP-41.2 rev8 |
