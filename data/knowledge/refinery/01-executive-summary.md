---
doc_id: refinery-technical-knowledge-base
chunk: 1
section: Executive Summary
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, overview]
---
## 1. Executive Summary

This dossier is the consolidated technical knowledge base for the Meridian Synthetic Refinery, a refining complex of 18 process areas, 58 registered equipment items and 224 field instruments. It covers the five-year reliability record from 2021-06 through 2026-09 and is written to be ingested as a retrieval corpus as well as read by an engineer.

The plant is a synthetic-but-complete refinery model: crude receiving and storage, desalting, crude and vacuum distillation, naphtha hydrotreating, catalytic reforming, fluid catalytic cracking, diesel hydrotreating, sulphur recovery, hydrogen, product storage, and the utility block (steam, cooling water, instrument air, flare, wastewater and safety systems). Every tag in this document resolves to a record in `equipment.json`; every instrument tag resolves to an entry in its owning unit's `sensors[]`.

### 1.1 State of the plant at 2026-09-30

All 58 registered units are running and reporting process data. No unit is in a tripped or shutdown state at the review date. Two registered assets carry a degraded condition that is being managed under an open work order:

| Tag | Name | Area | Criticality | Health | Status |
|---|---|---|---|---|---|
| P-1042 | Crude Charge Pump | Crude Distillation | Class 3 | 84/100 | WARNING |
| C-1071 | Reformer Recycle Compressor | Catalytic Reforming | Class 2 | 82/100 | WARNING |

### 1.2 The two live engineering problems

**Compressor C-3 (register twin C-1071, Recycle Gas Compressor).** Overall vibration on the drive-end bearing housing has risen to 6.8 mm/s RMS against a 5.7 mm/s learned baseline and a 5.8 mm/s 90-day rolling baseline, an increase of 18%. Energy is concentrated at 1x running speed with a stable 2x component, and the drive-end bearing housing temperature has risen from 68 degC to 79 degC. Inspection IR-204 records the survey and its spectral evidence; anomaly A-51 tracks the trend. The machine is inside its 7.1 mm/s alarm limit but outside the 10% deviation band that triggers daily monitoring, so vibration monitoring has been increased to once per shift and work order WO-8852 (drive-end bearing inspection) has been raised, gated by outage approval APR-231. The drive-end bearing was last replaced on 2025-03-16 under IR-198 and ME-198.

**Crude charge pump P-1042 (area cdu, criticality class 3).** Discharge pressure is running at 18.5 bar against a 17.0 bar operating alert threshold and a 16.2 bar baseline, a deviation of +14%. The transmitter envelope for PT-1042A is much wider (normal band 17.76 to 19.24 bar), so the excursion is an operating-limit breach rather than an instrument-envelope breach. Scenario `sc-sensor-failure` exercises the loss of PT-1042A itself, which is why the learned rule pins the process alert threshold at 17 bar rather than at the transmitter's own limits. Work order WO-8841 is open under SOP-14.2.

### 1.3 Where the reliability risk sits

The period generated 270 recorded maintenance events, 28 formal inspections, 48 tracked anomalies and 36 incident or event records. Rotating equipment (pumps, compressors and the one drive motor) accounts for the majority of unplanned corrective work; exchangers account for the largest single recurring degradation mechanism because fouling is progressive and tolerated by design until the duty loss is material.

### 1.4 What this document contains

Sections 2 and 3 describe the plant and its process units. Section 4 is the equipment register for all 58 units and states the health and next-maintenance derivation formula. Section 4b declares the register/overlay tag crosswalk. Section 5 instruments every unit. Sections 6 to 13 carry the operating envelope, the five-year maintenance history, inspection records, failure modes, safety and operating procedures, incident history and the reliability analysis. Sections 14 to 17 are the deep asset histories for C-3, P-1042, E-340 and T-118. Sections 18 to 22 carry the anomaly register, the intervention register, current status, lessons learned and recommended actions.
