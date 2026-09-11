---
doc_id: refinery-technical-knowledge-base
chunk: 11
section: Standard Operating Procedures
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, sop]
---
## 11. Standard Operating Procedures

This section registers the controlled operating procedures that govern the plant. 13 procedures are in force in the review period. Each is scoped to a specific equipment kind and failure mechanism, which is what makes different incidents retrieve different evidence instead of one universal procedure.

| Id | Title | Revision | Kind | Mechanism | Owner | Effective |
|---|---|---|---|---|---|---|
| OPS-03.2 | Refinery Unit Continuity and Compensating Monitoring | rev4 | column | degrade | Operations Standards | - |
| SOP-09.6 | Fired Heater and Furnace Thermal Excursion | rev5 | furnace | degrade | Operations Standards | - |
| SOP-14.2 | Field Instrument Failure and Isolation | rev6 | instrument | sensor_failure | Operations Standards | - |
| SOP-14.7 | Instrument Drift and Calibration Recovery | rev3 | instrument | instrument_drift | Operations Standards | - |
| SOP-18.3 | Motor and Drive Trip / Electrical Overload | rev4 | motor | overload | Operations Standards | - |
| SOP-22.1 | Centrifugal Pump Bearing Overheat and Vibration | rev5 | pump | bearing_overheat | Operations Standards | - |
| SOP-22.4 | Pump Cavitation and Suction Starvation | rev2 | pump | cavitation | Operations Standards | - |
| SOP-27.9 | Pressure Surge in Vessels, Columns and Headers | rev3 | vessel | pressure_surge | Operations Standards | - |
| SOP-31.5 | Mechanical Seal Leak and Hydrocarbon Release | rev7 | pump | seal_leak | Operations Standards | - |
| SOP-41.2 | Area Gas and Leak Detection Response | rev8 | safety | leak | Operations Standards | - |
| SOP-52.4 | Control Valve Sticking and Position Feedback Loss | rev2 | valve | stick | Operations Standards | - |
| SOP-07.3 | Rotating Equipment Vibration Response | rev4 | vibration | vibration | Maintenance Standards | 2026-05-22 |
| SOP-11.2 | Lockout / Tagout for Rotating Equipment | rev2 | lockout | lockout | Safety | 2026-01-30 |

### 11.1 Procedure scope statements

**OPS-03.2 Refinery Unit Continuity and Compensating Monitoring (rev4).** Continuity decisions across crude receiving and storage, desalting, crude and vacuum distillation, naphtha hydrotreating, reforming, catalytic cracking, diesel hydrotreating, sulphur recovery, hydrogen, product storage and utilities.

**SOP-09.6 Fired Heater and Furnace Thermal Excursion (rev5).** Fired heaters, furnaces and reheat furnaces with tube or outlet temperatures approaching the critical envelope, or with loss of a temperature measurement on a fired pass.

**SOP-14.2 Field Instrument Failure and Isolation (rev6).** Applies to any field transmitter reporting BAD quality, a frozen value, or a reading outside the configured critical envelope, on pressure, temperature, flow or level service.

**SOP-14.7 Instrument Drift and Calibration Recovery (rev3).** Governs transmitters whose reading walks away from correlated measurements without a corresponding process change — calibration drift rather than an abrupt instrument failure.

**SOP-18.3 Motor and Drive Trip / Electrical Overload (rev4).** Motors, drives and driven machines that trip on overload, or that draw current above the rated envelope while running.

**SOP-22.1 Centrifugal Pump Bearing Overheat and Vibration (rev5).** Centrifugal pumps and their drivers showing rising bearing temperature, rising vibration, or both, on any process service.

**SOP-22.4 Pump Cavitation and Suction Starvation (rev2).** Pumps exhibiting erratic discharge pressure, falling flow, and elevated vibration consistent with vapour formation at the impeller eye.

**SOP-27.9 Pressure Surge in Vessels, Columns and Headers (rev3).** Pressure vessels, separators, columns and headers experiencing a rapid rise in pressure toward or beyond the critical envelope.

**SOP-31.5 Mechanical Seal Leak and Hydrocarbon Release (rev7).** Any confirmed process leak from a mechanical seal, flange or pipe section, including releases detected only by an area gas or leak detector.

**SOP-41.2 Area Gas and Leak Detection Response (rev8).** Fixed gas detectors and liquid leak detectors in all process areas.

**SOP-52.4 Control Valve Sticking and Position Feedback Loss (rev2).** Control valves that fail to track their setpoint, and valves whose position transmitter disagrees with the commanded position.

**SOP-07.3 Rotating Equipment Vibration Response (rev4).** Defines the baseline deviation bands (0-10% routine, 10-25% daily monitoring plus a corrective work order within 72 h, above alarm limit reduce load and notify, above trip limit controlled shutdown), the daily monitoring requirement at section 4.2, the 15% / 1x bearing inspection trigger at section 4.3, and the manager approval gate for outages on criticality-high equipment at section 5.

**SOP-11.2 Lockout / Tagout for Rotating Equipment (rev2).** Six-step isolation and tagout sequence for rotating equipment maintenance.

### 11.2 Revision history in the period

SOP-07.3 rev4 took effect on 2026-05-22 and is the revision in force during the C-3 anomaly; its section 4.3 bearing inspection trigger and section 5 outage-approval gate are the two clauses that produced WO-8852 and APR-231. SOP-11.2 rev2 took effect on 2026-01-30. The instrument procedures (SOP-14.2 rev6, SOP-14.7 rev3) were re-issued as the pump and compressor instrument base was completed. SOP-41.2 rev8 is the most revised safety procedure in the corpus, reflecting the detector-heavy protective layer.

### 11.3 Procedure-to-failure-mode matrix

Retrieval quality depends on this matrix: an incident on a pump bearing must retrieve SOP-22.1, not the column procedure, and a transmitter failure must retrieve SOP-14.2 regardless of which unit it sits on.

| Mode id | Mode | Governing procedure | Equipment kinds | Family | Occurrences |
|---|---|---|---|---|---|
| sensor_failure | Sensor failure | SOP-14.2 | pressure | instrument | 1 |
| instrument_drift | Instrument drift | SOP-14.7 | temperature, pressure, flow | instrument | 1 |
| bearing_wear | Bearing wear | SOP-07.3 | pump, compressor, motor | rotating | 19 |
| cavitation | Pump cavitation | SOP-22.4 | pump | pump | 15 |
| bearing_overheat | Bearing overheating | SOP-22.1 | pump, motor, compressor | rotating | 23 |
| valve_stuck | Valve failure (stuck) | SOP-52.4 | valve | valve | 5 |
| seal_leak | Seal failure / oil leak | SOP-31.5 | pump, vessel | pump / vessel | 17 |
| pressure_surge | Pressure surge | SOP-27.9 | vessel, column, exchanger | static | 15 |
| trip | Equipment trip | SOP-18.3 | compressor, pump, motor | motor / drive | 27 |
| fouling | Heat exchanger fouling | fouling trend review | exchanger | exchanger | 7 |
| overload | Motor overload | SOP-18.3 | motor, conveyor | motor / drive | 2 |
| esd | Emergency shutdown | SOP-41.2 | safety | safety | 2 |

Two procedures are cross-cutting rather than mode-specific: SOP-11.2 (lockout / tagout) applies to every intervention on a rotating machine, and OPS-03.2 (unit continuity) applies to every decision to keep a unit running with a degraded instrument.
