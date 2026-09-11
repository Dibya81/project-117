# REFINERY TECHNICAL KNOWLEDGE BASE

Meridian Synthetic Refinery - five-year technical dossier (2021-06 .. 2026-09)

| Document control | |
|---|---|
| doc_id | `refinery-technical-knowledge-base` |
| generated_for | Project 117 |
| period | 2021-06 .. 2026-09 |
| cutoff | 2026-09-30 |
| register source | `apps/web/public/simulation/refinery/equipment.json` (58 units, 224 sensors) |
| overlay source | `data/demo/equipment/equipment.json` (6 assets) |
| sections | 23 |

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

## 2. Plant Overview

### 2.1 Identity

The plant is modelled as **Meridian Synthetic Refinery** (id `refinery`, industry `refining`). The model is a full-conversion refinery: it takes crude in at the receiving header, desalts and distils it, upgrades the naphtha and diesel fractions with hydrogen, reforms naphtha for octane, cracks vacuum gasoil in the FCC, recovers sulphur from acid gas, and ships naphtha, diesel and jet to product storage. The utility block supplies steam, cooling water, instrument air and plant air, and the safety block provides fire and gas detection and emergency shutdown.

### 2.2 Process areas

| Area id | Area name | Units | Instruments | Equipment kinds |
|---|---|---|---|---|
| crude-receiving | Crude Receiving | 4 | 19 | exchanger, pump, valve |
| crude-storage | Crude Storage | 3 | 6 | tank, valve |
| desalter | Desalter | 3 | 12 | pump, valve, vessel |
| cdu | Crude Distillation | 6 | 21 | column, exchanger, furnace, pump, valve, vessel |
| vdu | Vacuum Distillation | 4 | 18 | column, compressor, exchanger, pump |
| nht | Naphtha Hydrotreater | 4 | 15 | exchanger, pump, valve, vessel |
| reformer | Catalytic Reforming | 3 | 11 | compressor, furnace, vessel |
| fcc | FCC | 4 | 18 | compressor, exchanger, pump, vessel |
| dht | Diesel Hydrotreater | 3 | 13 | exchanger, pump, vessel |
| sulfur | Sulfur Recovery | 3 | 15 | compressor, pump, vessel |
| hydrogen | Hydrogen | 3 | 11 | compressor, furnace, vessel |
| product-storage | Product Storage | 4 | 13 | pump, tank |
| utilities | Utilities | 2 | 6 | compressor, utility |
| steam | Steam | 3 | 13 | furnace, motor, pump |
| cooling | Cooling Water | 3 | 15 | pump, utility |
| flare | Flare | 2 | 4 | utility, vessel |
| wastewater | Wastewater | 2 | 10 | pump, vessel |
| safety | Safety Systems | 2 | 4 | safety |

### 2.3 Process connectivity

The register carries 60 process lines between 58 units. Media in service are: air, amine, atm-resid, brine, control, crude, diesel, gas, hydrogen, jet, naphtha, recycle-gas, reformate, slurry, sour-gas, steam, vac-resid, vacuum-gas, vapor, vgo, wastewater, water. The excerpt below is the first block of the connectivity list; the full list is reproduced in the simulation dataset and is used by the plant graph.

| Line | Source | Target | Medium | Capacity | Kind |
|---|---|---|---|---|---|
| pl-001 | e-P-1001 | e-TK-1101 | crude | 140 | pipe |
| pl-002 | e-P-1002 | e-TK-1102 | crude | 140 | pipe |
| pl-003 | e-TK-1101 | e-V-1103 | crude | 120 | pipe |
| pl-004 | e-V-1103 | e-P-1042 | crude | 120 | pipe |
| pl-005 | e-P-1042 | e-E-1004 | crude | 115 | pipe |
| pl-006 | e-E-1004 | e-VS-1201 | crude | 110 | pipe |
| pl-007 | e-VS-1201 | e-F-1043 | crude | 105 | pipe |
| pl-008 | e-F-1043 | e-V-1047 | crude | 100 | pipe |
| pl-009 | e-V-1047 | e-COL-1044 | crude | 100 | pipe |
| pl-010 | e-COL-1044 | e-E-1045 | vapor | 60 | pipe |
| pl-011 | e-E-1045 | e-VS-1046 | naphtha | 45 | pipe |
| pl-012 | e-COL-1044 | e-P-1051 | atm-resid | 55 | pipe |
| pl-013 | e-P-1051 | e-COL-1052 | atm-resid | 55 | pipe |
| pl-014 | e-COL-1052 | e-C-1053 | vacuum-gas | 30 | pipe |
| pl-015 | e-COL-1052 | e-E-1054 | vac-resid | 40 | pipe |
| pl-016 | e-VS-1046 | e-P-1061 | naphtha | 40 | pipe |
| pl-017 | e-P-1061 | e-VS-1062 | naphtha | 40 | pipe |
| pl-018 | e-VS-1062 | e-E-1063 | naphtha | 38 | pipe |
| pl-019 | e-E-1063 | e-TK-1121 | naphtha | 38 | pipe |
| pl-020 | e-COL-1044 | e-P-1084 | vgo | 60 | pipe |

### 2.4 Operating basis

The plant runs continuously with a nominal two-shift operations roster and a day-shift maintenance crew. Turnaround work is planned by area and sequenced so that no more than one distillation train is out of service at a time. Crude and vacuum distillation cannot be left unattended with a lost column temperature or level measurement (OPS-03.2 rev4). Rotating equipment of criticality class 2 and above is governed by SOP-07.3 rev4 for vibration response.

### 2.5 Commissioning and operating age

The plant has been in production for approximately five years. **Commissioning window: 2021-06-01 to 2026-09-30.** First production was 2021-06-01, so the refinery is 5.3 years old at the 2026-09-30 cutoff. Every one of the 58 registered units was commissioned inside that window, and no unit predates the plant. Commissioning was staged in three build phases so that the crude train and its utilities came up first, distillation and reforming followed, and the conversion and treating units were the last to start.

| Build phase | Commissioning window | Areas | Units | Instruments |
|---|---|---|---|---|
| Phase 1 - crude train and utilities | 2021-06-01 .. 2021-09-30 | 9 | 24 | 89 |
| Phase 2 - distillation and reforming | 2021-07-01 .. 2022-01-31 | 6 | 24 | 89 |
| Phase 3 - conversion and treating | 2021-11-01 .. 2022-05-31 | 3 | 10 | 46 |

### 2.6 Instrumentation density

The 58 units carry 224 field instruments, an average of 3.9 per unit. The density is highest on the compressor trains and the seven-instrument pump blocks (pressure, flow, temperature, vibration, current and power), and lowest on utility packages and safety elements, which report a single status or detector channel.

## 3. Refinery Units

The 18 process areas are described below in process order. Each subsection gives the area duty, the media crossing its boundary, and the registered equipment that carries it.

### 3.1 Crude Receiving

Duty: receive tanker and pipeline crude and pump it to storage. Inbound media: crude. Outbound media: crude, wastewater. The area holds 4 registered units and 19 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1001 | Offloading Pump A | centrifugal process pump | Class 2 |
| P-1002 | Offloading Pump B | centrifugal process pump | Class 3 |
| V-1003 | Receiving Header Valve | control or block valve | Class 1 |
| E-1004 | Crude Preheater | shell-and-tube heat exchanger | Class 2 |

**Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

### 3.2 Crude Storage

Duty: hold crude inventory and feed the desalter at a controlled rate. Inbound media: crude. Outbound media: crude. The area holds 3 registered units and 6 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| TK-1101 | Crude Tank 1 | atmospheric storage tank | Class 2 |
| TK-1102 | Crude Tank 2 | atmospheric storage tank | Class 3 |
| V-1103 | Tank Outlet Valve | control or block valve | Class 1 |

**Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

### 3.3 Desalter

Duty: remove salts and water from crude ahead of distillation. Inbound media: crude. Outbound media: brine, crude. The area holds 3 registered units and 12 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| VS-1201 | Desalter Vessel | pressure vessel | Class 2 |
| P-1202 | Desalter Water Pump | centrifugal process pump | Class 3 |
| V-1203 | Brine Outlet Valve | control or block valve | Class 1 |

**Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

### 3.4 Crude Distillation

Duty: split desalted crude into naphtha, kerosene, diesel and atmospheric residue. Inbound media: control, crude, steam, water. Outbound media: atm-resid, crude, diesel, jet, naphtha, vgo. The area holds 6 registered units and 21 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1042 | Crude Charge Pump | centrifugal process pump | Class 3 |
| F-1043 | Crude Charge Heater | fired heater | Class 1 |
| COL-1044 | Atmospheric Column | fractionation column | Class 2 |
| E-1045 | Overhead Condenser | shell-and-tube heat exchanger | Class 3 |
| VS-1046 | Reflux Drum | pressure vessel | Class 1 |
| V-1047 | Column Feed Valve | control or block valve | Class 2 |

**Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

### 3.5 Vacuum Distillation

Duty: recover vacuum gasoil from atmospheric residue under vacuum. Inbound media: atm-resid, water. Outbound media: none (utility boundary). The area holds 4 registered units and 18 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1051 | VDU Feed Pump | centrifugal process pump | Class 2 |
| COL-1052 | Vacuum Column | fractionation column | Class 3 |
| C-1053 | Vacuum Ejector Compressor | rotating compressor | Class 1 |
| E-1054 | Vacuum Resid Cooler | shell-and-tube heat exchanger | Class 2 |

**Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

### 3.6 Naphtha Hydrotreater

Duty: hydrotreat naphtha to remove sulphur and nitrogen ahead of reforming. Inbound media: hydrogen, naphtha. Outbound media: naphtha. The area holds 4 registered units and 15 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1061 | NHT Feed Pump | centrifugal process pump | Class 2 |
| VS-1062 | NHT Reactor | pressure vessel | Class 3 |
| E-1063 | NHT Effluent Cooler | shell-and-tube heat exchanger | Class 1 |
| V-1064 | Stripper Level Valve | control or block valve | Class 2 |

**Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

### 3.7 Catalytic Reforming

Duty: raise naphtha octane and produce reformate and hydrogen-rich gas. Inbound media: naphtha. Outbound media: reformate. The area holds 3 registered units and 11 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| C-1071 | Reformer Recycle Compressor | rotating compressor | Class 2 |
| F-1072 | Reformer Charge Heater | fired heater | Class 3 |
| VS-1073 | Reformer Separator | pressure vessel | Class 1 |

**Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

### 3.8 FCC

Duty: crack vacuum gasoil to gasoline-range products and light gases. Inbound media: vgo. Outbound media: none (utility boundary). The area holds 4 registered units and 18 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| VS-1081 | FCC Reactor | pressure vessel | Class 2 |
| C-1082 | Main Air Blower | rotating compressor | Class 3 |
| E-1083 | FCC Slurry Cooler | shell-and-tube heat exchanger | Class 1 |
| P-1084 | FCC Feed Pump | centrifugal process pump | Class 2 |

**FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

### 3.9 Diesel Hydrotreater

Duty: hydrodesulphurise diesel to product specification. Inbound media: diesel, hydrogen. Outbound media: diesel. The area holds 3 registered units and 13 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1091 | DHT Feed Pump | centrifugal process pump | Class 2 |
| VS-1092 | DHT Reactor | pressure vessel | Class 3 |
| E-1093 | DHT Product Cooler | shell-and-tube heat exchanger | Class 1 |

**Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

### 3.10 Sulfur Recovery

Duty: recover elemental sulphur from amine acid gas. Inbound media: none (utility boundary). Outbound media: none (utility boundary). The area holds 3 registered units and 15 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| C-1125 | Sour Gas Compressor | rotating compressor | Class 3 |
| VS-1126 | Amine Contactor | pressure vessel | Class 1 |
| P-1127 | Lean Amine Pump | centrifugal process pump | Class 2 |

**Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

### 3.11 Hydrogen

Duty: generate and purify hydrogen for the hydrotreaters. Inbound media: none (utility boundary). Outbound media: hydrogen. The area holds 3 registered units and 11 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| F-1111 | SMR Furnace | fired heater | Class 2 |
| C-1112 | Hydrogen Compressor | rotating compressor | Class 3 |
| VS-1113 | PSA Vessel | pressure vessel | Class 1 |

**Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

### 3.12 Product Storage

Duty: hold finished naphtha, diesel and jet and load out product. Inbound media: diesel, jet, naphtha, reformate. Outbound media: none (utility boundary). The area holds 4 registered units and 13 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| TK-1121 | Naphtha Tank | atmospheric storage tank | Class 2 |
| TK-1122 | Diesel Tank | atmospheric storage tank | Class 3 |
| TK-1123 | Jet Tank | atmospheric storage tank | Class 1 |
| P-1124 | Product Loading Pump | centrifugal process pump | Class 2 |

**Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

### 3.13 Utilities

Duty: supply instrument air and plant air to the whole site. Inbound media: none (utility boundary). Outbound media: none (utility boundary). The area holds 2 registered units and 6 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| UT-1151 | Instrument Air Package | utility package | Class 2 |
| C-1152 | Plant Air Compressor | rotating compressor | Class 3 |

**Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

### 3.14 Steam

Duty: raise and distribute steam and return boiler feed water. Inbound media: none (utility boundary). Outbound media: steam. The area holds 3 registered units and 13 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| F-1141 | Steam Boiler | fired heater | Class 2 |
| P-1142 | Boiler Feed Pump | centrifugal process pump | Class 3 |
| M-1143 | BFD Fan Motor | electric drive motor | Class 1 |

**Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

### 3.15 Cooling Water

Duty: reject process heat to atmosphere and circulate cooling water. Inbound media: none (utility boundary). Outbound media: water. The area holds 3 registered units and 15 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1131 | Cooling Water Pump A | centrifugal process pump | Class 2 |
| P-1132 | Cooling Water Pump B | centrifugal process pump | Class 3 |
| UT-1133 | Cooling Tower Cell | utility package | Class 1 |

**Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

### 3.16 Flare

Duty: safely dispose of relief and upset hydrocarbon vapour. Inbound media: none (utility boundary). Outbound media: none (utility boundary). The area holds 2 registered units and 4 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| UT-1161 | Flare Stack | utility package | Class 2 |
| VS-1162 | Flare KO Drum | pressure vessel | Class 3 |

**Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

### 3.17 Wastewater

Duty: separate oil from process water before discharge. Inbound media: brine, wastewater. Outbound media: none (utility boundary). The area holds 2 registered units and 10 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| P-1171 | Wastewater Lift Pump | centrifugal process pump | Class 2 |
| VS-1172 | API Separator | pressure vessel | Class 3 |

**Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

### 3.18 Safety Systems

Duty: detect fire and gas and execute emergency shutdown. Inbound media: none (utility boundary). Outbound media: control. The area holds 2 registered units and 4 field instruments.

| Tag | Name | Role | Criticality class |
|---|---|---|---|
| ESD-1181 | Fire & Gas Panel | safety instrumented system element | Class 2 |
| ESD-1182 | Emergency Shutdown Valve | safety instrumented system element | Class 3 |

**Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

## 4. Equipment Register

The register below is the authoritative equipment list for the plant model. It contains one row for every registered unit: **58 units**, covering Meridian Synthetic Refinery. The `tag` column is the tag number used everywhere else in this document and in the simulation engine; it is the primary key.

**Column set (11 columns, in this order):** `Tag`, `Name`, `Kind`, `Area`, `Criticality`, `Commissioned`, `Manufacturer`, `Model`, `Last maint.`, `Next maint.`, `Health`. This is the register schema referenced by the manifest and by Section 5, which joins to it on `Tag` through its own `Equipment` column.

Derivation footnote. Four of the eleven columns are read verbatim from `equipment.json` and seven require a stated rule; all rules are deterministic and reproducible from the fixed seed, and none of them reads the clock.

* **Commissioned** - *normalized, not the register's `installed` value.* The register's `installed` field is a fabrication/legacy date that predates first production, which would contradict the plant's five-year operating age. This dossier therefore records a commissioning date normalized into the declared operating window (2021-06-01 to 2026-09-30), staged by the three build phases in Section 2.5. Within a phase, units of an area are spread evenly across the phase window so no two units share a date; C-1071 is pinned to 2021-06-14, the compression-train recommissioning date used throughout Section 14.
* **Manufacturer** - read verbatim from `equipment.json`'s `manufacturer` field. The register assigns each unit to one of six vendors: Atlas Pumps, SynthWorks, Flowdyne, Rotodyne, Helix Process and Vulcan Industrial. This document does not reassign vendors; the vendor split is the dataset's own.
* **Model** - *curated, not the register's `model` value.* Every `model` string in `equipment.json` is a masked-tag artefact - the unit's own tag with the final digit replaced by X (P-1001 -> `P-101X`, TK-1101 -> `TK-121X`) - so it is not a model number and is not reproduced here. Each unit instead carries a commercial designation matched to its kind and service role: API 610 / ISO 2858 pump families, compressor frame designations, TEMA exchanger sizes, floating-roof tank designations, valve trim designations, vessel and reactor tags, column internals, heater designations, a motor frame, utility packages and safety element designations. Only three strings are shared, and only because the units are genuinely the same model: `Flowserve HPX 6x8-15` (P-1001/P-1002), `KSB Etanorm 250-400` (P-1131/P-1132) and `CB&I FRT-5000` (TK-1101/TK-1102). All other 52 designations are unique.
* **Last maint.** - read verbatim from the register's `last_inspection` date.
* **Next maint.** - derived as `last_inspection + interval`, where the interval is 120 days for criticality class 1, 180 days for class 2 and 365 days for class 3. Next-maint dates are forecasts and may fall after the dossier cutoff.
* **Health** - derived as `base[class] - jitter`, where base is 88 (class 1), 91 (class 2) and 94 (class 3), and jitter is a seeded integer in 0..6 derived from `SHA-512(SEED:health:<tag>)`. Two assets carry a fixed override taken from the live console narrative rather than the formula: C-1071 = 82/100 (the C-3 twin) and P-1042 = 84/100.
* **Criticality** - read verbatim from the register's `criticality` field, presented as class 1 (highest consequence) to class 3 (standard).

### 4.1 Register

| Tag | Name | Kind | Area | Criticality | Commissioned | Manufacturer | Model | Last maint. | Next maint. | Health |
|---|---|---|---|---|---|---|---|---|---|---|
| P-1001 | Offloading Pump A | pump | Crude Receiving | Class 2 - high | 2021-06-01 | Atlas Pumps | Flowserve HPX 6x8-15 | 2026-02-03 | 2026-08-02 | 87/100 |
| P-1002 | Offloading Pump B | pump | Crude Receiving | Class 3 - standard | 2021-07-01 | SynthWorks | Flowserve HPX 6x8-15 | 2026-03-04 | 2027-03-04 | 89/100 |
| V-1003 | Receiving Header Valve | valve | Crude Receiving | Class 1 - highest consequence | 2021-07-31 | Flowdyne | Fisher ED-667 | 2026-04-05 | 2026-08-03 | 88/100 |
| E-1004 | Crude Preheater | exchanger | Crude Receiving | Class 2 - high | 2021-08-30 | Rotodyne | TEMA BEM 1100-450-25-2 | 2026-05-06 | 2026-11-02 | 87/100 |
| TK-1101 | Crude Tank 1 | tank | Crude Storage | Class 2 - high | 2021-06-01 | Helix Process | CB&I FRT-5000 | 2026-06-22 | 2026-12-19 | 88/100 |
| TK-1102 | Crude Tank 2 | tank | Crude Storage | Class 3 - standard | 2021-07-11 | Vulcan Industrial | CB&I FRT-5000 | 2026-07-23 | 2027-07-23 | 93/100 |
| V-1103 | Tank Outlet Valve | valve | Crude Storage | Class 1 - highest consequence | 2021-08-20 | Atlas Pumps | Samson 241-1 | 2026-08-24 | 2026-12-22 | 88/100 |
| VS-1201 | Desalter Vessel | vessel | Desalter | Class 2 - high | 2021-06-01 | Flowdyne | Babcock & Wilcox PV-2100 | 2026-02-14 | 2026-08-13 | 88/100 |
| P-1202 | Desalter Water Pump | pump | Desalter | Class 3 - standard | 2021-07-11 | Rotodyne | Wilo CronoLine IL 100/160 | 2026-03-15 | 2027-03-15 | 90/100 |
| V-1203 | Brine Outlet Valve | valve | Desalter | Class 1 - highest consequence | 2021-08-20 | Helix Process | Copes-Vulcan D-100-3 | 2026-04-16 | 2026-08-14 | 88/100 |
| P-1042 | Crude Charge Pump | pump | Crude Distillation | Class 3 - standard | 2021-07-01 | Vulcan Industrial | Sulzer MSD 8x10x15 | 2026-03-17 | 2027-03-17 | 84/100 |
| F-1043 | Crude Charge Heater | furnace | Crude Distillation | Class 1 - highest consequence | 2021-08-05 | Atlas Pumps | Foster Wheeler H-1201 | 2026-04-18 | 2026-08-16 | 86/100 |
| COL-1044 | Atmospheric Column | column | Crude Distillation | Class 2 - high | 2021-09-10 | SynthWorks | Koch-Glitsch FRI-2400 | 2026-05-19 | 2026-11-15 | 90/100 |
| E-1045 | Overhead Condenser | exchanger | Crude Distillation | Class 3 - standard | 2021-10-16 | Flowdyne | API Basco 500-300-2 | 2026-06-20 | 2027-06-20 | 94/100 |
| VS-1046 | Reflux Drum | vessel | Crude Distillation | Class 1 - highest consequence | 2021-11-20 | Rotodyne | Chart VPS-1800 | 2026-07-21 | 2026-11-18 | 88/100 |
| V-1047 | Column Feed Valve | valve | Crude Distillation | Class 2 - high | 2021-12-26 | Helix Process | Valtek Mark One 6x4 | 2026-08-22 | 2027-02-18 | 85/100 |
| P-1051 | VDU Feed Pump | pump | Vacuum Distillation | Class 2 - high | 2021-07-01 | Flowdyne | Sulzer MSD 6x8x14 | 2026-04-26 | 2026-10-23 | 88/100 |
| COL-1052 | Vacuum Column | column | Vacuum Distillation | Class 3 - standard | 2021-08-23 | Rotodyne | Sulzer Mellapak 250Y-2600 | 2026-05-27 | 2027-05-27 | 90/100 |
| C-1053 | Vacuum Ejector Compressor | compressor | Vacuum Distillation | Class 1 - highest consequence | 2021-10-16 | Helix Process | Kobelco 3M7-6 | 2026-06-01 | 2026-09-29 | 86/100 |
| E-1054 | Vacuum Resid Cooler | exchanger | Vacuum Distillation | Class 2 - high | 2021-12-08 | Vulcan Industrial | Sondex S7-1200-25 | 2026-07-02 | 2026-12-29 | 86/100 |
| P-1061 | NHT Feed Pump | pump | Naphtha Hydrotreater | Class 2 - high | 2021-07-01 | Atlas Pumps | Goulds 3196 MTX 4x6-10 | 2026-06-09 | 2026-12-06 | 88/100 |
| VS-1062 | NHT Reactor | vessel | Naphtha Hydrotreater | Class 3 - standard | 2021-08-23 | SynthWorks | L&T PV-4500 | 2026-07-10 | 2027-07-10 | 92/100 |
| E-1063 | NHT Effluent Cooler | exchanger | Naphtha Hydrotreater | Class 1 - highest consequence | 2021-10-16 | Flowdyne | Alfa Laval ST-340 | 2026-08-11 | 2026-12-09 | 84/100 |
| V-1064 | Stripper Level Valve | valve | Naphtha Hydrotreater | Class 2 - high | 2021-12-08 | Rotodyne | Masoneilan 21000-6 | 2026-01-12 | 2026-07-11 | 89/100 |
| C-1071 | Reformer Recycle Compressor | compressor | Catalytic Reforming | Class 2 - high | 2021-06-14 | Helix Process | Elliott 29M9-6 | 2026-08-19 | 2027-02-15 | 82/100 |
| F-1072 | Reformer Charge Heater | furnace | Catalytic Reforming | Class 3 - standard | 2021-09-10 | Vulcan Industrial | Selas D-1050 | 2026-01-20 | 2027-01-20 | 88/100 |
| VS-1073 | Reformer Separator | vessel | Catalytic Reforming | Class 1 - highest consequence | 2021-11-20 | Atlas Pumps | Godrej PV-2400 | 2026-02-21 | 2026-06-21 | 85/100 |
| VS-1081 | FCC Reactor | vessel | FCC | Class 2 - high | 2021-11-01 | Flowdyne | CB&I PV-6200 | 2026-02-02 | 2026-08-01 | 86/100 |
| C-1082 | Main Air Blower | compressor | FCC | Class 3 - standard | 2021-12-23 | Rotodyne | MAN RG 45/25 | 2026-03-03 | 2027-03-03 | 94/100 |
| E-1083 | FCC Slurry Cooler | exchanger | FCC | Class 1 - highest consequence | 2022-02-14 | Helix Process | Thermal Engineering 900 BEM | 2026-04-04 | 2026-08-02 | 85/100 |
| P-1084 | FCC Feed Pump | pump | FCC | Class 2 - high | 2022-04-08 | Vulcan Industrial | Ruhrpumpen API 610 OH2 6x8-15 | 2026-05-05 | 2026-11-01 | 88/100 |
| P-1091 | DHT Feed Pump | pump | Diesel Hydrotreater | Class 2 - high | 2021-11-01 | Atlas Pumps | Durco Mark 3 4x6-10 | 2026-04-12 | 2026-10-09 | 90/100 |
| VS-1092 | DHT Reactor | vessel | Diesel Hydrotreater | Class 3 - standard | 2022-01-10 | SynthWorks | Larsen & Toubro PV-4000 | 2026-05-13 | 2027-05-13 | 91/100 |
| E-1093 | DHT Product Cooler | exchanger | Diesel Hydrotreater | Class 1 - highest consequence | 2022-03-21 | Flowdyne | GEA Ecoflex NT 250S | 2026-06-14 | 2026-10-12 | 87/100 |
| C-1125 | Sour Gas Compressor | compressor | Sulfur Recovery | Class 3 - standard | 2021-11-01 | Helix Process | Siemens STC-SV 080 | 2026-06-19 | 2027-06-19 | 92/100 |
| VS-1126 | Amine Contactor | vessel | Sulfur Recovery | Class 1 - highest consequence | 2022-01-10 | Vulcan Industrial | ISGEC PV-2800 | 2026-07-20 | 2026-11-17 | 84/100 |
| P-1127 | Lean Amine Pump | pump | Sulfur Recovery | Class 2 - high | 2022-03-21 | Atlas Pumps | Dickow NMM 100/250 | 2026-08-21 | 2027-02-17 | 87/100 |
| F-1111 | SMR Furnace | furnace | Hydrogen | Class 2 - high | 2021-07-01 | Flowdyne | UOP F-4500 | 2026-08-05 | 2027-02-01 | 86/100 |
| C-1112 | Hydrogen Compressor | compressor | Hydrogen | Class 3 - standard | 2021-09-10 | Rotodyne | Dresser-Rand DATUM D-8 | 2026-01-06 | 2027-01-06 | 92/100 |
| VS-1113 | PSA Vessel | vessel | Hydrogen | Class 1 - highest consequence | 2021-11-20 | Helix Process | Kobe Steel PV-1800 | 2026-02-07 | 2026-06-07 | 88/100 |
| TK-1121 | Naphtha Tank | tank | Product Storage | Class 2 - high | 2021-07-01 | Atlas Pumps | BHEL FRT-118 | 2026-02-15 | 2026-08-14 | 89/100 |
| TK-1122 | Diesel Tank | tank | Product Storage | Class 3 - standard | 2021-08-23 | SynthWorks | PECOFacet EFRT-3200 | 2026-03-16 | 2027-03-16 | 91/100 |
| TK-1123 | Jet Tank | tank | Product Storage | Class 1 - highest consequence | 2021-10-16 | Flowdyne | Chicago Bridge EFRT-2000 | 2026-04-17 | 2026-08-15 | 87/100 |
| P-1124 | Product Loading Pump | pump | Product Storage | Class 2 - high | 2021-12-08 | Rotodyne | KSB Etanorm 080-200 | 2026-05-18 | 2026-11-14 | 91/100 |
| P-1131 | Cooling Water Pump A | pump | Cooling Water | Class 2 - high | 2021-06-01 | Helix Process | KSB Etanorm 250-400 | 2026-04-25 | 2026-10-22 | 91/100 |
| P-1132 | Cooling Water Pump B | pump | Cooling Water | Class 3 - standard | 2021-07-11 | Vulcan Industrial | KSB Etanorm 250-400 | 2026-05-26 | 2027-05-26 | 90/100 |
| UT-1133 | Cooling Tower Cell | utility | Cooling Water | Class 1 - highest consequence | 2021-08-20 | Atlas Pumps | SPX Marley NC-8412 | 2026-06-27 | 2026-10-25 | 87/100 |
| F-1141 | Steam Boiler | furnace | Steam | Class 2 - high | 2021-06-01 | Flowdyne | Born Heaters B-2200 | 2026-06-08 | 2026-12-05 | 88/100 |
| P-1142 | Boiler Feed Pump | pump | Steam | Class 3 - standard | 2021-07-11 | Rotodyne | Grundfos NK 125-400 | 2026-07-09 | 2027-07-09 | 89/100 |
| M-1143 | BFD Fan Motor | motor | Steam | Class 1 - highest consequence | 2021-08-20 | Helix Process | Siemens 1LA8 450 | 2026-08-10 | 2026-12-08 | 83/100 |
| UT-1151 | Instrument Air Package | utility | Utilities | Class 2 - high | 2021-06-01 | Atlas Pumps | Ingersoll Rand SSR-200 | 2026-08-18 | 2027-02-14 | 88/100 |
| C-1152 | Plant Air Compressor | compressor | Utilities | Class 3 - standard | 2021-07-31 | SynthWorks | Atlas Copco GA 315 VSD | 2026-01-19 | 2027-01-19 | 91/100 |
| UT-1161 | Flare Stack | utility | Flare | Class 2 - high | 2021-06-01 | Helix Process | John Zink Z-500 | 2026-02-01 | 2026-07-31 | 90/100 |
| VS-1162 | Flare KO Drum | vessel | Flare | Class 3 - standard | 2021-07-31 | Vulcan Industrial | Bharat Heavy PV-1600 | 2026-03-02 | 2027-03-02 | 91/100 |
| P-1171 | Wastewater Lift Pump | pump | Wastewater | Class 2 - high | 2021-06-01 | Flowdyne | Ebara 150x125 FS4JA | 2026-04-11 | 2026-10-08 | 91/100 |
| VS-1172 | API Separator | vessel | Wastewater | Class 3 - standard | 2021-07-31 | Rotodyne | Tata Projects PV-3400 | 2026-05-12 | 2027-05-12 | 89/100 |
| ESD-1181 | Fire & Gas Panel | safety | Safety Systems | Class 2 - high | 2021-06-01 | Atlas Pumps | Honeywell FSC-500 | 2026-06-21 | 2026-12-18 | 88/100 |
| ESD-1182 | Emergency Shutdown Valve | safety | Safety Systems | Class 3 - standard | 2021-07-31 | SynthWorks | Fisher 657-ED | 2026-07-22 | 2027-07-22 | 90/100 |

### 4.2 Distribution by area

| Area | Units | Class 1 | Class 2 | Class 3 |
|---|---|---|---|---|
| Crude Receiving | 4 | 1 | 2 | 1 |
| Crude Storage | 3 | 1 | 1 | 1 |
| Desalter | 3 | 1 | 1 | 1 |
| Crude Distillation | 6 | 2 | 2 | 2 |
| Vacuum Distillation | 4 | 1 | 2 | 1 |
| Naphtha Hydrotreater | 4 | 1 | 2 | 1 |
| Catalytic Reforming | 3 | 1 | 1 | 1 |
| FCC | 4 | 1 | 2 | 1 |
| Diesel Hydrotreater | 3 | 1 | 1 | 1 |
| Sulfur Recovery | 3 | 1 | 1 | 1 |
| Hydrogen | 3 | 1 | 1 | 1 |
| Product Storage | 4 | 1 | 2 | 1 |
| Utilities | 2 | 0 | 1 | 1 |
| Steam | 3 | 1 | 1 | 1 |
| Cooling Water | 3 | 1 | 1 | 1 |
| Flare | 2 | 0 | 1 | 1 |
| Wastewater | 2 | 0 | 1 | 1 |
| Safety Systems | 2 | 0 | 1 | 1 |

### 4.3 Register notes

* Commissioned dates span 2021-06-01 to 2022-04-08. The oldest registered assets are P-1001 (2021-06-01), TK-1101 (2021-06-01); the newest are P-1127 (2022-03-21), P-1084 (2022-04-08). The spread is the staged build described in Section 2.5, not piecemeal replacement.
* Manufacturer spread is narrow by design: Atlas Pumps, SynthWorks, Flowdyne, Rotodyne, Helix Process and Vulcan Industrial between them supply every unit. Spares strategy follows the manufacturer, not the area. Vendors are the register's own assignment and are reproduced without change.
* Criticality class 1 units (15 of 58) are the distillation columns' fired heaters, the FCC air blower, the SMR furnace and the emergency shutdown elements. They drive the turnaround sequence.
* Health is a condition score, not an availability figure; availability is in Section 13.

### 4.4 Area commentary

The same 18 units read by area, with the maintenance and condition record for each area summarised from the registers in Sections 7 and 13.

### 4.4.1 Crude Receiving

**Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

### 4.4.2 Crude Storage

**Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

### 4.4.3 Desalter

**Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

### 4.4.4 Crude Distillation

**Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

### 4.4.5 Vacuum Distillation

**Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

### 4.4.6 Naphtha Hydrotreater

**Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

### 4.4.7 Catalytic Reforming

**Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

### 4.4.8 FCC

**FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

### 4.4.9 Diesel Hydrotreater

**Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

### 4.4.10 Sulfur Recovery

**Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

### 4.4.11 Hydrogen

**Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

### 4.4.12 Product Storage

**Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

### 4.4.13 Utilities

**Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

### 4.4.14 Steam

**Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

### 4.4.15 Cooling Water

**Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

### 4.4.16 Flare

**Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

### 4.4.17 Wastewater

**Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

### 4.4.18 Safety Systems

**Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

## 4b. Register ↔ Overlay Crosswalk

The console ships two equipment vocabularies and this document uses both. They are declared here so that no tag in the dossier has to be inferred.

* **Register vocabulary** - the 58 tag numbers in `apps/web/public/simulation/refinery/equipment.json`. This is the live simulation register and the authority for Sections 4 and 5.
* **Overlay vocabulary** - the 6 legacy assets in `data/demo/equipment/equipment.json`, the U-200 console/demo dataset: C-3, P-1042, V-2210, T-118, E-340, P-2051. These tags carry the narrative that already exists in the app (compressor C-3, pump P-1042, vessel V-2210, tank T-118, exchanger E-340, pump P-2051) and are used as the primary key in Sections 14 to 17 and wherever the console story is told.

The crosswalk below maps each overlay asset to its register counterpart. `confidence` is deliberately explicit: **exact** means the same tag string exists in the register; **twin** means a distinct register tag carries the same machine signature or duty; **partial** means the register asset covers only part of the overlay service and the mapping must not be read as equivalence.

| Overlay tag | Overlay name | Register tag | Register name | Confidence | Basis and caveat |
|---|---|---|---|---|---|
| C-3 | Recycle Gas Compressor | C-1071 | Reformer Recycle Compressor | twin | Register twin carries the same machine signature: VIB-1071 nominal 5.7 mm/s, RPM-1071 nominal 8,840 rpm, TT-1071 nominal 79 degC. |
| P-1042 | Feed Charge Pump | P-1042 | Crude Charge Pump | exact | Same tag in both vocabularies; register area cdu, criticality class 3. |
| E-340 | Feed/Effluent Heat Exchanger | E-1063 | NHT Effluent Cooler | twin | Hydrotreater effluent exchanger; register carries inlet/outlet temperature and tube-side flow. |
| T-118 | Intermediate Storage Tank | TK-1121 | Naphtha Tank | twin | Product-storage tank with level and temperature instrumentation. |
| V-2210 | Product Separator Vessel | V-1047 | Column Feed Valve | partial | Register asset is the process valve with actuator position feedback; the overlay vessel itself has no register tag number. |
| P-2051 | Product Transfer Pump | P-1124 | Product Loading Pump | partial | Same duty family; overlay pump is under maintenance, register pump is in service. |

### 4b.1 Why C-3 maps to C-1071

The mapping is not a guess. The register twin for C-3 is C-1071, the Reformer Recycle Compressor, and its instrumentation reproduces the console machine signature exactly: VIB-1071 nominal 5.7 mm/s (the learned C-3 baseline), RPM-1071 nominal 8,840 rpm (the console's 8,800 rpm running speed) and TT-1071 nominal 79 degC (the current drive-end bearing temperature). This is the strongest of the six mappings and is treated as an exact twin in this document.

### 4b.2 Partial mappings

V-2210 maps only partially. The overlay asset is a product separator vessel whose live issue is a high level excursion (87% against an 80% setpoint), while the register counterpart V-1047 is a process valve carrying actuator position feedback. The two are related by service position in the U-200 train, not by equipment identity, and V-2210's level excursion is therefore reported against the overlay tag with the register tag named only as a locator. P-2051 maps only partially for the same reason: the register asset P-1124 is in service, while the overlay asset is recorded as under maintenance, so condition data must not be copied between them.

### 4b.3 How to read a tag in this document

If a tag appears in the register vocabulary it is a live register asset and its row in Section 4 is authoritative. If it appears in the overlay vocabulary it is a console asset and its record in `data/demo/equipment/equipment.json` is authoritative; the register counterpart named here is used only to locate the asset in the physical plant. Where both appear together, the convention in this document is `register-tag (overlay-tag)`, for example `C-1071 (C-3)`.

## 5. Instrumentation

The register carries **224 field instruments** across 58 units, every one listed below. A sensor's `normal` band is the register's `normal_min..normal_max`; `warning` is `warning_min..warning_max` and `critical` is `critical_min..critical_max`. By construction each band strictly contains the previous one, so a warning range always sits outside the normal range and a critical range always outside the warning range. Latched detector channels (gas, leak) are one-sided by design: their lower thresholds collapse onto zero because a healthy detector reads zero.

**Column set (8 columns, in this order):** `Sensor tag`, `Equipment`, `Measurement`, `Unit`, `Nominal`, `Normal range`, `Warning range`, `Critical range`. This instrumentation schema joins to the 11-column equipment register in Section 4 on `Equipment` -> `Tag`; the `Tag` values here are exactly the register tags, so the two tables agree unit for unit.

Instrumentation by measurement type:

| Measurement | Instruments |
|---|---|
| pressure | 61 |
| temperature | 53 |
| flow | 23 |
| vibration | 20 |
| level | 17 |
| current | 15 |
| power | 15 |
| rpm | 7 |
| gas | 6 |
| position | 5 |
| leak | 2 |

### 5.1 Field instrument register

| Sensor tag | Equipment | Measurement | Unit | Nominal | Normal range | Warning range | Critical range |
|---|---|---|---|---|---|---|---|
| PT-1053D | C-1053 | pressure | bar | 13.65 | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| PT-1053S | C-1053 | pressure | bar | 4.76 | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| RPM-1053 | C-1053 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1053 | C-1053 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1053 | C-1053 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| PT-1071D | C-1071 | pressure | bar | 19.5 | 18.72 .. 20.28 | 17.55 .. 21.06 | 15.99 .. 22.62 |
| PT-1071S | C-1071 | pressure | bar | 6.8 | 6.53 .. 7.07 | 6.12 .. 7.34 | 5.58 .. 7.89 |
| RPM-1071 | C-1071 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1071 | C-1071 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1071 | C-1071 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| PT-1082D | C-1082 | pressure | bar | 25.35 | 24.34 .. 26.36 | 22.82 .. 27.38 | 20.79 .. 29.41 |
| PT-1082S | C-1082 | pressure | bar | 8.84 | 8.49 .. 9.19 | 7.96 .. 9.55 | 7.25 .. 10.25 |
| RPM-1082 | C-1082 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1082 | C-1082 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1082 | C-1082 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| PT-1112D | C-1112 | pressure | bar | 17.55 | 16.85 .. 18.25 | 15.8 .. 18.95 | 14.39 .. 20.36 |
| PT-1112S | C-1112 | pressure | bar | 6.12 | 5.88 .. 6.36 | 5.51 .. 6.61 | 5.02 .. 7.1 |
| RPM-1112 | C-1112 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1112 | C-1112 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1112 | C-1112 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| PT-1125D | C-1125 | pressure | bar | 13.65 | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| PT-1125S | C-1125 | pressure | bar | 4.76 | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| RPM-1125 | C-1125 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1125 | C-1125 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1125 | C-1125 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| PT-1152D | C-1152 | pressure | bar | 13.65 | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| PT-1152S | C-1152 | pressure | bar | 4.76 | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| RPM-1152 | C-1152 | rpm | rpm | 8840 | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| TT-1152 | C-1152 | temperature | °C | 79 | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VIB-1152 | C-1152 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| LT-1044 | COL-1044 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1044 | COL-1044 | pressure | bar | 9.5 | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| TT-1044 | COL-1044 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| LT-1052 | COL-1052 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1052 | COL-1052 | pressure | bar | 9.5 | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| TT-1052 | COL-1052 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1004 | E-1004 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1004I | E-1004 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1004O | E-1004 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1045 | E-1045 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1045I | E-1045 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1045O | E-1045 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1054 | E-1054 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1054I | E-1054 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1054O | E-1054 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1063 | E-1063 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1063I | E-1063 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1063O | E-1063 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1083 | E-1083 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1083I | E-1083 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1083O | E-1083 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| FT-1093 | E-1093 | flow | m³/h | 88 | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| TT-1093I | E-1093 | temperature | °C | 210 | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| TT-1093O | E-1093 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| GD-1181 | ESD-1181 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| LK-1181 | ESD-1181 | leak | 0/1 | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| GD-1182 | ESD-1182 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| LK-1182 | ESD-1182 | leak | 0/1 | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| GD-1043 | F-1043 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| PT-1043 | F-1043 | pressure | bar | 3.4 | 3.26 .. 3.54 | 3.06 .. 3.67 | 2.79 .. 3.94 |
| TT-1043 | F-1043 | temperature | °C | 620 | 595.2 .. 644.8 | 558 .. 669.6 | 508.4 .. 719.2 |
| GD-1072 | F-1072 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| PT-1072 | F-1072 | pressure | bar | 3.06 | 2.94 .. 3.18 | 2.75 .. 3.3 | 2.51 .. 3.55 |
| TT-1072 | F-1072 | temperature | °C | 558 | 535.68 .. 580.32 | 502.2 .. 602.64 | 457.56 .. 647.28 |
| GD-1111 | F-1111 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| PT-1111 | F-1111 | pressure | bar | 3.74 | 3.59 .. 3.89 | 3.37 .. 4.04 | 3.07 .. 4.34 |
| TT-1111 | F-1111 | temperature | °C | 682 | 654.72 .. 709.28 | 613.8 .. 736.56 | 559.24 .. 791.12 |
| GD-1141 | F-1141 | gas | ppm | 0 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| PT-1141 | F-1141 | pressure | bar | 3.4 | 3.26 .. 3.54 | 3.06 .. 3.67 | 2.79 .. 3.94 |
| TT-1141 | F-1141 | temperature | °C | 620 | 595.2 .. 644.8 | 558 .. 669.6 | 508.4 .. 719.2 |
| A-1143 | M-1143 | current | A | 76.8 | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| KW-1143 | M-1143 | power | kW | 368 | 353.28 .. 382.72 | 331.2 .. 397.44 | 301.76 .. 426.88 |
| RPM-1143 | M-1143 | rpm | rpm | 1480 | 1420.8 .. 1539.2 | 1332 .. 1598.4 | 1213.6 .. 1716.8 |
| A-1001 | P-1001 | current | A | 92.4 | 88.7 .. 96.1 | 83.16 .. 99.79 | 75.77 .. 107.18 |
| FT-1001 | P-1001 | flow | m³/h | 105.6 | 101.38 .. 109.82 | 95.04 .. 114.05 | 86.59 .. 122.5 |
| KW-1001 | P-1001 | power | kW | 451 | 432.96 .. 469.04 | 405.9 .. 487.08 | 369.82 .. 523.16 |
| PT-1001A | P-1001 | pressure | bar | 20.35 | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| PT-1001B | P-1001 | pressure | bar | 20.35 | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| TT-1001 | P-1001 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1001 | P-1001 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1002 | P-1002 | current | A | 92.4 | 88.7 .. 96.1 | 83.16 .. 99.79 | 75.77 .. 107.18 |
| FT-1002 | P-1002 | flow | m³/h | 105.6 | 101.38 .. 109.82 | 95.04 .. 114.05 | 86.59 .. 122.5 |
| KW-1002 | P-1002 | power | kW | 451 | 432.96 .. 469.04 | 405.9 .. 487.08 | 369.82 .. 523.16 |
| PT-1002A | P-1002 | pressure | bar | 20.35 | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| PT-1002B | P-1002 | pressure | bar | 20.35 | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| TT-1002 | P-1002 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1002 | P-1002 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1042 | P-1042 | current | A | 84 | 80.64 .. 87.36 | 75.6 .. 90.72 | 68.88 .. 97.44 |
| FT-1042 | P-1042 | flow | m³/h | 96 | 92.16 .. 99.84 | 86.4 .. 103.68 | 78.72 .. 111.36 |
| KW-1042 | P-1042 | power | kW | 410 | 393.6 .. 426.4 | 369 .. 442.8 | 336.2 .. 475.6 |
| PT-1042A | P-1042 | pressure | bar | 18.5 | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| PT-1042B | P-1042 | pressure | bar | 18.5 | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| TT-1042 | P-1042 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1042 | P-1042 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1051 | P-1051 | current | A | 75.6 | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| FT-1051 | P-1051 | flow | m³/h | 86.4 | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| KW-1051 | P-1051 | power | kW | 369 | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| PT-1051A | P-1051 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| PT-1051B | P-1051 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| TT-1051 | P-1051 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1051 | P-1051 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1061 | P-1061 | current | A | 67.2 | 64.51 .. 69.89 | 60.48 .. 72.58 | 55.1 .. 77.95 |
| FT-1061 | P-1061 | flow | m³/h | 76.8 | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| KW-1061 | P-1061 | power | kW | 328 | 314.88 .. 341.12 | 295.2 .. 354.24 | 268.96 .. 380.48 |
| PT-1061A | P-1061 | pressure | bar | 14.8 | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| PT-1061B | P-1061 | pressure | bar | 14.8 | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| TT-1061 | P-1061 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1061 | P-1061 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1084 | P-1084 | current | A | 100.8 | 96.77 .. 104.83 | 90.72 .. 108.86 | 82.66 .. 116.93 |
| FT-1084 | P-1084 | flow | m³/h | 115.2 | 110.59 .. 119.81 | 103.68 .. 124.42 | 94.46 .. 133.63 |
| KW-1084 | P-1084 | power | kW | 492 | 472.32 .. 511.68 | 442.8 .. 531.36 | 403.44 .. 570.72 |
| PT-1084A | P-1084 | pressure | bar | 22.2 | 21.31 .. 23.09 | 19.98 .. 23.98 | 18.2 .. 25.75 |
| PT-1084B | P-1084 | pressure | bar | 22.2 | 21.31 .. 23.09 | 19.98 .. 23.98 | 18.2 .. 25.75 |
| TT-1084 | P-1084 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1084 | P-1084 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1091 | P-1091 | current | A | 75.6 | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| FT-1091 | P-1091 | flow | m³/h | 86.4 | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| KW-1091 | P-1091 | power | kW | 369 | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| PT-1091A | P-1091 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| PT-1091B | P-1091 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| TT-1091 | P-1091 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1091 | P-1091 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1124 | P-1124 | current | A | 67.2 | 64.51 .. 69.89 | 60.48 .. 72.58 | 55.1 .. 77.95 |
| FT-1124 | P-1124 | flow | m³/h | 76.8 | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| KW-1124 | P-1124 | power | kW | 328 | 314.88 .. 341.12 | 295.2 .. 354.24 | 268.96 .. 380.48 |
| PT-1124A | P-1124 | pressure | bar | 14.8 | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| PT-1124B | P-1124 | pressure | bar | 14.8 | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| TT-1124 | P-1124 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1124 | P-1124 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1127 | P-1127 | current | A | 50.4 | 48.38 .. 52.42 | 45.36 .. 54.43 | 41.33 .. 58.46 |
| FT-1127 | P-1127 | flow | m³/h | 57.6 | 55.3 .. 59.9 | 51.84 .. 62.21 | 47.23 .. 66.82 |
| KW-1127 | P-1127 | power | kW | 246 | 236.16 .. 255.84 | 221.4 .. 265.68 | 201.72 .. 285.36 |
| PT-1127A | P-1127 | pressure | bar | 11.1 | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| PT-1127B | P-1127 | pressure | bar | 11.1 | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| TT-1127 | P-1127 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1127 | P-1127 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1131 | P-1131 | current | A | 109.2 | 104.83 .. 113.57 | 98.28 .. 117.94 | 89.54 .. 126.67 |
| FT-1131 | P-1131 | flow | m³/h | 124.8 | 119.81 .. 129.79 | 112.32 .. 134.78 | 102.34 .. 144.77 |
| KW-1131 | P-1131 | power | kW | 533 | 511.68 .. 554.32 | 479.7 .. 575.64 | 437.06 .. 618.28 |
| PT-1131A | P-1131 | pressure | bar | 24.05 | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| PT-1131B | P-1131 | pressure | bar | 24.05 | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| TT-1131 | P-1131 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1131 | P-1131 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1132 | P-1132 | current | A | 109.2 | 104.83 .. 113.57 | 98.28 .. 117.94 | 89.54 .. 126.67 |
| FT-1132 | P-1132 | flow | m³/h | 124.8 | 119.81 .. 129.79 | 112.32 .. 134.78 | 102.34 .. 144.77 |
| KW-1132 | P-1132 | power | kW | 533 | 511.68 .. 554.32 | 479.7 .. 575.64 | 437.06 .. 618.28 |
| PT-1132A | P-1132 | pressure | bar | 24.05 | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| PT-1132B | P-1132 | pressure | bar | 24.05 | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| TT-1132 | P-1132 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1132 | P-1132 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1142 | P-1142 | current | A | 75.6 | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| FT-1142 | P-1142 | flow | m³/h | 86.4 | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| KW-1142 | P-1142 | power | kW | 369 | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| PT-1142A | P-1142 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| PT-1142B | P-1142 | pressure | bar | 16.65 | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| TT-1142 | P-1142 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1142 | P-1142 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1171 | P-1171 | current | A | 42 | 40.32 .. 43.68 | 37.8 .. 45.36 | 34.44 .. 48.72 |
| FT-1171 | P-1171 | flow | m³/h | 48 | 46.08 .. 49.92 | 43.2 .. 51.84 | 39.36 .. 55.68 |
| KW-1171 | P-1171 | power | kW | 205 | 196.8 .. 213.2 | 184.5 .. 221.4 | 168.1 .. 237.8 |
| PT-1171A | P-1171 | pressure | bar | 9.25 | 8.88 .. 9.62 | 8.33 .. 9.99 | 7.58 .. 10.73 |
| PT-1171B | P-1171 | pressure | bar | 9.25 | 8.88 .. 9.62 | 8.33 .. 9.99 | 7.58 .. 10.73 |
| TT-1171 | P-1171 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1171 | P-1171 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| A-1202 | P-1202 | current | A | 50.4 | 48.38 .. 52.42 | 45.36 .. 54.43 | 41.33 .. 58.46 |
| FT-1202 | P-1202 | flow | m³/h | 57.6 | 55.3 .. 59.9 | 51.84 .. 62.21 | 47.23 .. 66.82 |
| KW-1202 | P-1202 | power | kW | 246 | 236.16 .. 255.84 | 221.4 .. 265.68 | 201.72 .. 285.36 |
| PT-1202A | P-1202 | pressure | bar | 11.1 | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| PT-1202B | P-1202 | pressure | bar | 11.1 | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| TT-1202 | P-1202 | temperature | °C | 73 | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| VIB-1202 | P-1202 | vibration | mm/s | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| LT-1101 | TK-1101 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1101 | TK-1101 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| LT-1102 | TK-1102 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1102 | TK-1102 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| LT-1121 | TK-1121 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1121 | TK-1121 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| LT-1122 | TK-1122 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1122 | TK-1122 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| LT-1123 | TK-1123 | level | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TT-1123 | TK-1123 | temperature | °C | 41 | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| FT-1133 | UT-1133 | flow | m³/h | 144 | 138.24 .. 149.76 | 129.6 .. 155.52 | 118.08 .. 167.04 |
| FT-1151 | UT-1151 | flow | m³/h | 96 | 92.16 .. 99.84 | 86.4 .. 103.68 | 78.72 .. 111.36 |
| FT-1161 | UT-1161 | flow | m³/h | 48 | 46.08 .. 49.92 | 43.2 .. 51.84 | 39.36 .. 55.68 |
| PT-1003 | V-1003 | pressure | bar | 14.5 | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| ZT-1003 | V-1003 | position | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| PT-1047 | V-1047 | pressure | bar | 14.5 | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| ZT-1047 | V-1047 | position | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| PT-1064 | V-1064 | pressure | bar | 14.5 | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| ZT-1064 | V-1064 | position | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| PT-1103 | V-1103 | pressure | bar | 14.5 | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| ZT-1103 | V-1103 | position | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| PT-1203 | V-1203 | pressure | bar | 14.5 | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| ZT-1203 | V-1203 | position | % | 62 | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| LT-1046 | VS-1046 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1046 | VS-1046 | pressure | bar | 7.6 | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| TT-1046 | VS-1046 | temperature | °C | 150.4 | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| LT-1062 | VS-1062 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1062 | VS-1062 | pressure | bar | 11.4 | 10.94 .. 11.86 | 10.26 .. 12.31 | 9.35 .. 13.22 |
| TT-1062 | VS-1062 | temperature | °C | 225.6 | 216.58 .. 234.62 | 203.04 .. 243.65 | 184.99 .. 261.7 |
| LT-1073 | VS-1073 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1073 | VS-1073 | pressure | bar | 7.6 | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| TT-1073 | VS-1073 | temperature | °C | 150.4 | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| LT-1081 | VS-1081 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1081 | VS-1081 | pressure | bar | 13.3 | 12.77 .. 13.83 | 11.97 .. 14.36 | 10.91 .. 15.43 |
| TT-1081 | VS-1081 | temperature | °C | 263.2 | 252.67 .. 273.73 | 236.88 .. 284.26 | 215.82 .. 305.31 |
| LT-1092 | VS-1092 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1092 | VS-1092 | pressure | bar | 10.45 | 10.03 .. 10.87 | 9.41 .. 11.29 | 8.57 .. 12.12 |
| TT-1092 | VS-1092 | temperature | °C | 206.8 | 198.53 .. 215.07 | 186.12 .. 223.34 | 169.58 .. 239.89 |
| LT-1113 | VS-1113 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1113 | VS-1113 | pressure | bar | 6.65 | 6.38 .. 6.92 | 5.98 .. 7.18 | 5.45 .. 7.71 |
| TT-1113 | VS-1113 | temperature | °C | 131.6 | 126.34 .. 136.86 | 118.44 .. 142.13 | 107.91 .. 152.66 |
| LT-1126 | VS-1126 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1126 | VS-1126 | pressure | bar | 7.6 | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| TT-1126 | VS-1126 | temperature | °C | 150.4 | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| LT-1162 | VS-1162 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1162 | VS-1162 | pressure | bar | 4.75 | 4.56 .. 4.94 | 4.28 .. 5.13 | 3.89 .. 5.51 |
| TT-1162 | VS-1162 | temperature | °C | 94 | 90.24 .. 97.76 | 84.6 .. 101.52 | 77.08 .. 109.04 |
| LT-1172 | VS-1172 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1172 | VS-1172 | pressure | bar | 5.7 | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| TT-1172 | VS-1172 | temperature | °C | 112.8 | 108.29 .. 117.31 | 101.52 .. 121.82 | 92.5 .. 130.85 |
| LT-1201 | VS-1201 | level | % | 55 | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| PT-1201 | VS-1201 | pressure | bar | 9.5 | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| TT-1201 | VS-1201 | temperature | °C | 188 | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |

### 5.2 Latched detectors

8 channels are latched point detectors. Healthy state is zero and a trip latches at full scale until the release is cleared and the device is reset. A detector reading zero is healthy, not failed, and must never be treated as an envelope violation (SOP-41.2 rev8).

| Sensor tag | Equipment | Measurement | Unit | Nominal | Critical band |
|---|---|---|---|---|---|
| GD-1043 | F-1043 | gas | ppm | 0 | 0.5 .. 1 |
| GD-1072 | F-1072 | gas | ppm | 0 | 0.5 .. 1 |
| GD-1111 | F-1111 | gas | ppm | 0 | 0.5 .. 1 |
| GD-1141 | F-1141 | gas | ppm | 0 | 0.5 .. 1 |
| GD-1181 | ESD-1181 | gas | ppm | 0 | 0.5 .. 1 |
| GD-1182 | ESD-1182 | gas | ppm | 0 | 0.5 .. 1 |
| LK-1181 | ESD-1181 | leak | 0/1 | 0 | 0.5 .. 1 |
| LK-1182 | ESD-1182 | leak | 0/1 | 0 | 0.5 .. 1 |

### 5.3 Legacy overlay instrumentation (U-200 console dataset)

The overlay assets report named signals rather than register sensor tags. They are reproduced verbatim from `data/demo/equipment/equipment.json` so the C-3, P-1042, E-340, T-118 and V-2210 narrative can be read against its own instrumentation. These signal names are not sensor tags and must not be searched as if they were.

| Asset | Name | Signal | Value | Unit | Baseline | Limit | Deviation | State |
|---|---|---|---|---|---|---|---|---|
| C-3 | Recycle Gas Compressor | vibration_overall | 6.8 | mm/s | 5.8 | 7.1 | +18% | warning |
| C-3 | Recycle Gas Compressor | bearing_temp_de | 79 | degC | 68 | 85 | +16% | warning |
| C-3 | Recycle Gas Compressor | discharge_pressure | 42.1 | bar | 42 | 46 | +0% | normal |
| P-1042 | Feed Charge Pump | discharge_pressure | 18.5 | bar | 16.2 | 17 | +14% | exceeded |
| V-2210 | Product Separator Vessel | level | 87 | % | 68 | 80 | +28% | exceeded |
| T-118 | Intermediate Storage Tank | level | 54 | % | 55 | 90 | -2% | normal |
| E-340 | Feed/Effluent Heat Exchanger | delta_p | 0.42 | bar | 0.4 | 0.75 | +5% | normal |
| P-2051 | Product Transfer Pump | vibration_overall | 0 | mm/s | 3.1 | 6 | -100% | offline |

### 5.4 Loop calibration register

Calibration intervals are set by measurement type: latched detectors every 90 days, level and vibration every 180 days, pressure, temperature, flow, position and speed annually, and electrical measurements on a 730-day cycle. `last calibration` and `next due` are derived deterministically from the cutoff date and the interval; `next due` is a forecast and may fall after the dossier cutoff. Tolerance is the acceptance band applied after calibration, and a loop is not returned to automatic until the instrument agrees with its reference across the normal range for ten consecutive scans.

| Sensor tag | Equipment | Area | Measurement | Interval | Last calibration | Next due | Tolerance |
|---|---|---|---|---|---|---|---|
| PT-1053D | C-1053 | Vacuum Distillation | pressure | 365 d | 2025-10-12 | 2026-10-12 | 0.5% of span |
| PT-1053S | C-1053 | Vacuum Distillation | pressure | 365 d | 2026-04-01 | 2027-04-01 | 0.5% of span |
| RPM-1053 | C-1053 | Vacuum Distillation | rpm | 365 d | 2026-02-12 | 2027-02-12 | 0.5% of reading |
| TT-1053 | C-1053 | Vacuum Distillation | temperature | 365 d | 2026-09-02 | 2027-09-02 | 1.0 degC |
| VIB-1053 | C-1053 | Vacuum Distillation | vibration | 180 d | 2026-05-01 | 2026-10-28 | 2.0% of reading |
| PT-1071D | C-1071 | Catalytic Reforming | pressure | 365 d | 2026-06-01 | 2027-06-01 | 0.5% of span |
| PT-1071S | C-1071 | Catalytic Reforming | pressure | 365 d | 2026-09-14 | 2027-09-14 | 0.5% of span |
| RPM-1071 | C-1071 | Catalytic Reforming | rpm | 365 d | 2026-09-25 | 2027-09-25 | 0.5% of reading |
| TT-1071 | C-1071 | Catalytic Reforming | temperature | 365 d | 2026-09-19 | 2027-09-19 | 1.0 degC |
| VIB-1071 | C-1071 | Catalytic Reforming | vibration | 180 d | 2026-05-31 | 2026-11-27 | 2.0% of reading |
| PT-1082D | C-1082 | FCC | pressure | 365 d | 2026-04-19 | 2027-04-19 | 0.5% of span |
| PT-1082S | C-1082 | FCC | pressure | 365 d | 2025-12-10 | 2026-12-10 | 0.5% of span |
| RPM-1082 | C-1082 | FCC | rpm | 365 d | 2026-07-21 | 2027-07-21 | 0.5% of reading |
| TT-1082 | C-1082 | FCC | temperature | 365 d | 2026-09-24 | 2027-09-24 | 1.0 degC |
| VIB-1082 | C-1082 | FCC | vibration | 180 d | 2026-07-05 | 2027-01-01 | 2.0% of reading |
| PT-1112D | C-1112 | Hydrogen | pressure | 365 d | 2025-11-17 | 2026-11-17 | 0.5% of span |
| PT-1112S | C-1112 | Hydrogen | pressure | 365 d | 2025-11-30 | 2026-11-30 | 0.5% of span |
| RPM-1112 | C-1112 | Hydrogen | rpm | 365 d | 2026-05-06 | 2027-05-06 | 0.5% of reading |
| TT-1112 | C-1112 | Hydrogen | temperature | 365 d | 2025-10-20 | 2026-10-20 | 1.0 degC |
| VIB-1112 | C-1112 | Hydrogen | vibration | 180 d | 2026-08-12 | 2027-02-08 | 2.0% of reading |
| PT-1125D | C-1125 | Sulfur Recovery | pressure | 365 d | 2026-07-30 | 2027-07-30 | 0.5% of span |
| PT-1125S | C-1125 | Sulfur Recovery | pressure | 365 d | 2026-08-30 | 2027-08-30 | 0.5% of span |
| RPM-1125 | C-1125 | Sulfur Recovery | rpm | 365 d | 2025-12-26 | 2026-12-26 | 0.5% of reading |
| TT-1125 | C-1125 | Sulfur Recovery | temperature | 365 d | 2026-04-07 | 2027-04-07 | 1.0 degC |
| VIB-1125 | C-1125 | Sulfur Recovery | vibration | 180 d | 2026-09-13 | 2027-03-12 | 2.0% of reading |
| PT-1152D | C-1152 | Utilities | pressure | 365 d | 2026-01-11 | 2027-01-11 | 0.5% of span |
| PT-1152S | C-1152 | Utilities | pressure | 365 d | 2026-06-06 | 2027-06-06 | 0.5% of span |
| RPM-1152 | C-1152 | Utilities | rpm | 365 d | 2025-10-26 | 2026-10-26 | 0.5% of reading |
| TT-1152 | C-1152 | Utilities | temperature | 365 d | 2026-04-23 | 2027-04-23 | 1.0 degC |
| VIB-1152 | C-1152 | Utilities | vibration | 180 d | 2026-06-22 | 2026-12-19 | 2.0% of reading |
| LT-1044 | COL-1044 | Crude Distillation | level | 180 d | 2026-05-22 | 2026-11-18 | 0.5% of range |
| PT-1044 | COL-1044 | Crude Distillation | pressure | 365 d | 2026-03-18 | 2027-03-18 | 0.5% of span |
| TT-1044 | COL-1044 | Crude Distillation | temperature | 365 d | 2026-01-09 | 2027-01-09 | 1.0 degC |
| LT-1052 | COL-1052 | Vacuum Distillation | level | 180 d | 2026-04-14 | 2026-10-11 | 0.5% of range |
| PT-1052 | COL-1052 | Vacuum Distillation | pressure | 365 d | 2026-02-08 | 2027-02-08 | 0.5% of span |
| TT-1052 | COL-1052 | Vacuum Distillation | temperature | 365 d | 2026-07-26 | 2027-07-26 | 1.0 degC |
| FT-1004 | E-1004 | Crude Receiving | flow | 365 d | 2026-08-29 | 2027-08-29 | 1.0% of rate |
| TT-1004I | E-1004 | Crude Receiving | temperature | 365 d | 2026-03-08 | 2027-03-08 | 1.0 degC |
| TT-1004O | E-1004 | Crude Receiving | temperature | 365 d | 2026-05-29 | 2027-05-29 | 1.0 degC |
| FT-1045 | E-1045 | Crude Distillation | flow | 365 d | 2025-11-08 | 2026-11-08 | 1.0% of rate |
| TT-1045I | E-1045 | Crude Distillation | temperature | 365 d | 2026-01-26 | 2027-01-26 | 1.0 degC |
| TT-1045O | E-1045 | Crude Distillation | temperature | 365 d | 2026-08-14 | 2027-08-14 | 1.0 degC |
| FT-1054 | E-1054 | Vacuum Distillation | flow | 365 d | 2026-01-03 | 2027-01-03 | 1.0% of rate |
| TT-1054I | E-1054 | Vacuum Distillation | temperature | 365 d | 2025-12-24 | 2026-12-24 | 1.0 degC |
| TT-1054O | E-1054 | Vacuum Distillation | temperature | 365 d | 2026-06-19 | 2027-06-19 | 1.0 degC |
| FT-1063 | E-1063 | Naphtha Hydrotreater | flow | 365 d | 2025-11-02 | 2026-11-02 | 1.0% of rate |
| TT-1063I | E-1063 | Naphtha Hydrotreater | temperature | 365 d | 2026-05-24 | 2027-05-24 | 1.0 degC |
| TT-1063O | E-1063 | Naphtha Hydrotreater | temperature | 365 d | 2026-03-16 | 2027-03-16 | 1.0 degC |
| FT-1083 | E-1083 | FCC | flow | 365 d | 2026-03-03 | 2027-03-03 | 1.0% of rate |
| TT-1083I | E-1083 | FCC | temperature | 365 d | 2025-12-08 | 2026-12-08 | 1.0 degC |
| TT-1083O | E-1083 | FCC | temperature | 365 d | 2026-01-14 | 2027-01-14 | 1.0 degC |
| FT-1093 | E-1093 | Diesel Hydrotreater | flow | 365 d | 2026-05-10 | 2027-05-10 | 1.0% of rate |
| TT-1093I | E-1093 | Diesel Hydrotreater | temperature | 365 d | 2026-02-24 | 2027-02-24 | 1.0 degC |
| TT-1093O | E-1093 | Diesel Hydrotreater | temperature | 365 d | 2026-07-31 | 2027-07-31 | 1.0 degC |
| GD-1181 | ESD-1181 | Safety Systems | gas | 90 d | 2026-07-27 | 2026-10-25 | 2.0% LEL |
| LK-1181 | ESD-1181 | Safety Systems | leak | 90 d | 2026-09-01 | 2026-11-30 | pass / fail |
| GD-1182 | ESD-1182 | Safety Systems | gas | 90 d | 2026-08-07 | 2026-11-05 | 2.0% LEL |
| LK-1182 | ESD-1182 | Safety Systems | leak | 90 d | 2026-08-14 | 2026-11-12 | pass / fail |
| GD-1043 | F-1043 | Crude Distillation | gas | 90 d | 2026-08-08 | 2026-11-06 | 2.0% LEL |
| PT-1043 | F-1043 | Crude Distillation | pressure | 365 d | 2026-01-22 | 2027-01-22 | 0.5% of span |
| TT-1043 | F-1043 | Crude Distillation | temperature | 365 d | 2026-05-27 | 2027-05-27 | 1.0 degC |
| GD-1072 | F-1072 | Catalytic Reforming | gas | 90 d | 2026-09-07 | 2026-12-06 | 2.0% LEL |
| PT-1072 | F-1072 | Catalytic Reforming | pressure | 365 d | 2026-01-05 | 2027-01-05 | 0.5% of span |
| TT-1072 | F-1072 | Catalytic Reforming | temperature | 365 d | 2026-06-04 | 2027-06-04 | 1.0 degC |
| GD-1111 | F-1111 | Hydrogen | gas | 90 d | 2026-09-14 | 2026-12-13 | 2.0% LEL |
| PT-1111 | F-1111 | Hydrogen | pressure | 365 d | 2026-08-29 | 2027-08-29 | 0.5% of span |
| TT-1111 | F-1111 | Hydrogen | temperature | 365 d | 2025-11-18 | 2026-11-18 | 1.0 degC |
| GD-1141 | F-1141 | Steam | gas | 90 d | 2026-08-27 | 2026-11-25 | 2.0% LEL |
| PT-1141 | F-1141 | Steam | pressure | 365 d | 2026-08-10 | 2027-08-10 | 0.5% of span |
| TT-1141 | F-1141 | Steam | temperature | 365 d | 2026-05-09 | 2027-05-09 | 1.0 degC |
| A-1143 | M-1143 | Steam | current | 730 d | 2025-12-30 | 2027-12-30 | 1.0% of range |
| KW-1143 | M-1143 | Steam | power | 730 d | 2026-03-29 | 2028-03-28 | 1.5% of range |
| RPM-1143 | M-1143 | Steam | rpm | 365 d | 2026-08-29 | 2027-08-29 | 0.5% of reading |
| A-1001 | P-1001 | Crude Receiving | current | 730 d | 2026-05-20 | 2028-05-19 | 1.0% of range |
| FT-1001 | P-1001 | Crude Receiving | flow | 365 d | 2026-06-22 | 2027-06-22 | 1.0% of rate |
| KW-1001 | P-1001 | Crude Receiving | power | 730 d | 2026-09-19 | 2028-09-18 | 1.5% of range |
| PT-1001A | P-1001 | Crude Receiving | pressure | 365 d | 2026-05-24 | 2027-05-24 | 0.5% of span |
| PT-1001B | P-1001 | Crude Receiving | pressure | 365 d | 2026-08-14 | 2027-08-14 | 0.5% of span |
| TT-1001 | P-1001 | Crude Receiving | temperature | 365 d | 2026-06-24 | 2027-06-24 | 1.0 degC |
| VIB-1001 | P-1001 | Crude Receiving | vibration | 180 d | 2026-04-19 | 2026-10-16 | 2.0% of reading |
| A-1002 | P-1002 | Crude Receiving | current | 730 d | 2025-11-13 | 2027-11-13 | 1.0% of range |
| FT-1002 | P-1002 | Crude Receiving | flow | 365 d | 2026-08-16 | 2027-08-16 | 1.0% of rate |
| KW-1002 | P-1002 | Crude Receiving | power | 730 d | 2025-10-06 | 2027-10-06 | 1.5% of range |
| PT-1002A | P-1002 | Crude Receiving | pressure | 365 d | 2026-05-15 | 2027-05-15 | 0.5% of span |
| PT-1002B | P-1002 | Crude Receiving | pressure | 365 d | 2026-05-26 | 2027-05-26 | 0.5% of span |
| TT-1002 | P-1002 | Crude Receiving | temperature | 365 d | 2025-11-23 | 2026-11-23 | 1.0 degC |
| VIB-1002 | P-1002 | Crude Receiving | vibration | 180 d | 2026-08-20 | 2027-02-16 | 2.0% of reading |
| A-1042 | P-1042 | Crude Distillation | current | 730 d | 2026-04-08 | 2028-04-07 | 1.0% of range |
| FT-1042 | P-1042 | Crude Distillation | flow | 365 d | 2025-11-28 | 2026-11-28 | 1.0% of rate |
| KW-1042 | P-1042 | Crude Distillation | power | 730 d | 2025-07-15 | 2027-07-15 | 1.5% of range |
| PT-1042A | P-1042 | Crude Distillation | pressure | 365 d | 2026-08-25 | 2027-08-25 | 0.5% of span |
| PT-1042B | P-1042 | Crude Distillation | pressure | 365 d | 2026-07-28 | 2027-07-28 | 0.5% of span |
| TT-1042 | P-1042 | Crude Distillation | temperature | 365 d | 2025-12-23 | 2026-12-23 | 1.0 degC |
| VIB-1042 | P-1042 | Crude Distillation | vibration | 180 d | 2026-05-03 | 2026-10-30 | 2.0% of reading |
| A-1051 | P-1051 | Vacuum Distillation | current | 730 d | 2026-07-22 | 2028-07-21 | 1.0% of range |
| FT-1051 | P-1051 | Vacuum Distillation | flow | 365 d | 2026-04-14 | 2027-04-14 | 1.0% of rate |
| KW-1051 | P-1051 | Vacuum Distillation | power | 730 d | 2026-03-21 | 2028-03-20 | 1.5% of range |
| PT-1051A | P-1051 | Vacuum Distillation | pressure | 365 d | 2026-01-09 | 2027-01-09 | 0.5% of span |
| PT-1051B | P-1051 | Vacuum Distillation | pressure | 365 d | 2025-12-09 | 2026-12-09 | 0.5% of span |
| TT-1051 | P-1051 | Vacuum Distillation | temperature | 365 d | 2026-09-22 | 2027-09-22 | 1.0 degC |
| VIB-1051 | P-1051 | Vacuum Distillation | vibration | 180 d | 2026-09-23 | 2027-03-22 | 2.0% of reading |
| A-1061 | P-1061 | Naphtha Hydrotreater | current | 730 d | 2026-01-02 | 2028-01-02 | 1.0% of range |
| FT-1061 | P-1061 | Naphtha Hydrotreater | flow | 365 d | 2026-05-16 | 2027-05-16 | 1.0% of rate |
| KW-1061 | P-1061 | Naphtha Hydrotreater | power | 730 d | 2024-10-31 | 2026-10-31 | 1.5% of range |
| PT-1061A | P-1061 | Naphtha Hydrotreater | pressure | 365 d | 2025-10-23 | 2026-10-23 | 0.5% of span |
| PT-1061B | P-1061 | Naphtha Hydrotreater | pressure | 365 d | 2025-10-21 | 2026-10-21 | 0.5% of span |
| TT-1061 | P-1061 | Naphtha Hydrotreater | temperature | 365 d | 2026-04-22 | 2027-04-22 | 1.0 degC |
| VIB-1061 | P-1061 | Naphtha Hydrotreater | vibration | 180 d | 2026-05-10 | 2026-11-06 | 2.0% of reading |
| A-1084 | P-1084 | FCC | current | 730 d | 2025-04-20 | 2027-04-20 | 1.0% of range |
| FT-1084 | P-1084 | FCC | flow | 365 d | 2026-08-23 | 2027-08-23 | 1.0% of rate |
| KW-1084 | P-1084 | FCC | power | 730 d | 2025-05-21 | 2027-05-21 | 1.5% of range |
| PT-1084A | P-1084 | FCC | pressure | 365 d | 2026-04-04 | 2027-04-04 | 0.5% of span |
| PT-1084B | P-1084 | FCC | pressure | 365 d | 2026-07-29 | 2027-07-29 | 0.5% of span |
| TT-1084 | P-1084 | FCC | temperature | 365 d | 2025-12-12 | 2026-12-12 | 1.0 degC |
| VIB-1084 | P-1084 | FCC | vibration | 180 d | 2026-08-29 | 2027-02-25 | 2.0% of reading |
| A-1091 | P-1091 | Diesel Hydrotreater | current | 730 d | 2026-03-13 | 2028-03-12 | 1.0% of range |
| FT-1091 | P-1091 | Diesel Hydrotreater | flow | 365 d | 2026-06-09 | 2027-06-09 | 1.0% of rate |
| KW-1091 | P-1091 | Diesel Hydrotreater | power | 730 d | 2025-07-31 | 2027-07-31 | 1.5% of range |
| PT-1091A | P-1091 | Diesel Hydrotreater | pressure | 365 d | 2026-05-11 | 2027-05-11 | 0.5% of span |
| PT-1091B | P-1091 | Diesel Hydrotreater | pressure | 365 d | 2025-11-13 | 2026-11-13 | 0.5% of span |
| TT-1091 | P-1091 | Diesel Hydrotreater | temperature | 365 d | 2026-02-25 | 2027-02-25 | 1.0 degC |
| VIB-1091 | P-1091 | Diesel Hydrotreater | vibration | 180 d | 2026-06-17 | 2026-12-14 | 2.0% of reading |
| A-1124 | P-1124 | Product Storage | current | 730 d | 2026-03-15 | 2028-03-14 | 1.0% of range |
| FT-1124 | P-1124 | Product Storage | flow | 365 d | 2026-01-26 | 2027-01-26 | 1.0% of rate |
| KW-1124 | P-1124 | Product Storage | power | 730 d | 2025-02-20 | 2027-02-20 | 1.5% of range |
| PT-1124A | P-1124 | Product Storage | pressure | 365 d | 2026-03-14 | 2027-03-14 | 0.5% of span |
| PT-1124B | P-1124 | Product Storage | pressure | 365 d | 2026-08-27 | 2027-08-27 | 0.5% of span |
| TT-1124 | P-1124 | Product Storage | temperature | 365 d | 2025-12-19 | 2026-12-19 | 1.0 degC |
| VIB-1124 | P-1124 | Product Storage | vibration | 180 d | 2026-07-10 | 2027-01-06 | 2.0% of reading |
| A-1127 | P-1127 | Sulfur Recovery | current | 730 d | 2025-09-25 | 2027-09-25 | 1.0% of range |
| FT-1127 | P-1127 | Sulfur Recovery | flow | 365 d | 2026-06-18 | 2027-06-18 | 1.0% of rate |
| KW-1127 | P-1127 | Sulfur Recovery | power | 730 d | 2026-01-21 | 2028-01-21 | 1.5% of range |
| PT-1127A | P-1127 | Sulfur Recovery | pressure | 365 d | 2026-01-17 | 2027-01-17 | 0.5% of span |
| PT-1127B | P-1127 | Sulfur Recovery | pressure | 365 d | 2025-11-25 | 2026-11-25 | 0.5% of span |
| TT-1127 | P-1127 | Sulfur Recovery | temperature | 365 d | 2026-01-18 | 2027-01-18 | 1.0 degC |
| VIB-1127 | P-1127 | Sulfur Recovery | vibration | 180 d | 2026-05-05 | 2026-11-01 | 2.0% of reading |
| A-1131 | P-1131 | Cooling Water | current | 730 d | 2025-02-03 | 2027-02-03 | 1.0% of range |
| FT-1131 | P-1131 | Cooling Water | flow | 365 d | 2026-01-18 | 2027-01-18 | 1.0% of rate |
| KW-1131 | P-1131 | Cooling Water | power | 730 d | 2025-10-19 | 2027-10-19 | 1.5% of range |
| PT-1131A | P-1131 | Cooling Water | pressure | 365 d | 2026-09-19 | 2027-09-19 | 0.5% of span |
| PT-1131B | P-1131 | Cooling Water | pressure | 365 d | 2026-02-25 | 2027-02-25 | 0.5% of span |
| TT-1131 | P-1131 | Cooling Water | temperature | 365 d | 2026-07-05 | 2027-07-05 | 1.0 degC |
| VIB-1131 | P-1131 | Cooling Water | vibration | 180 d | 2026-08-27 | 2027-02-23 | 2.0% of reading |
| A-1132 | P-1132 | Cooling Water | current | 730 d | 2025-12-01 | 2027-12-01 | 1.0% of range |
| FT-1132 | P-1132 | Cooling Water | flow | 365 d | 2026-08-16 | 2027-08-16 | 1.0% of rate |
| KW-1132 | P-1132 | Cooling Water | power | 730 d | 2026-02-08 | 2028-02-08 | 1.5% of range |
| PT-1132A | P-1132 | Cooling Water | pressure | 365 d | 2025-12-30 | 2026-12-30 | 0.5% of span |
| PT-1132B | P-1132 | Cooling Water | pressure | 365 d | 2026-05-17 | 2027-05-17 | 0.5% of span |
| TT-1132 | P-1132 | Cooling Water | temperature | 365 d | 2026-07-14 | 2027-07-14 | 1.0 degC |
| VIB-1132 | P-1132 | Cooling Water | vibration | 180 d | 2026-04-14 | 2026-10-11 | 2.0% of reading |
| A-1142 | P-1142 | Steam | current | 730 d | 2024-10-15 | 2026-10-15 | 1.0% of range |
| FT-1142 | P-1142 | Steam | flow | 365 d | 2025-12-06 | 2026-12-06 | 1.0% of rate |
| KW-1142 | P-1142 | Steam | power | 730 d | 2025-03-24 | 2027-03-24 | 1.5% of range |
| PT-1142A | P-1142 | Steam | pressure | 365 d | 2026-07-12 | 2027-07-12 | 0.5% of span |
| PT-1142B | P-1142 | Steam | pressure | 365 d | 2026-08-25 | 2027-08-25 | 0.5% of span |
| TT-1142 | P-1142 | Steam | temperature | 365 d | 2025-10-12 | 2026-10-12 | 1.0 degC |
| VIB-1142 | P-1142 | Steam | vibration | 180 d | 2026-06-17 | 2026-12-14 | 2.0% of reading |
| A-1171 | P-1171 | Wastewater | current | 730 d | 2024-12-14 | 2026-12-14 | 1.0% of range |
| FT-1171 | P-1171 | Wastewater | flow | 365 d | 2026-03-03 | 2027-03-03 | 1.0% of rate |
| KW-1171 | P-1171 | Wastewater | power | 730 d | 2026-06-06 | 2028-06-05 | 1.5% of range |
| PT-1171A | P-1171 | Wastewater | pressure | 365 d | 2025-10-30 | 2026-10-30 | 0.5% of span |
| PT-1171B | P-1171 | Wastewater | pressure | 365 d | 2025-12-14 | 2026-12-14 | 0.5% of span |
| TT-1171 | P-1171 | Wastewater | temperature | 365 d | 2026-05-25 | 2027-05-25 | 1.0 degC |
| VIB-1171 | P-1171 | Wastewater | vibration | 180 d | 2026-07-25 | 2027-01-21 | 2.0% of reading |
| A-1202 | P-1202 | Desalter | current | 730 d | 2025-04-12 | 2027-04-12 | 1.0% of range |
| FT-1202 | P-1202 | Desalter | flow | 365 d | 2026-04-09 | 2027-04-09 | 1.0% of rate |
| KW-1202 | P-1202 | Desalter | power | 730 d | 2026-01-26 | 2028-01-26 | 1.5% of range |
| PT-1202A | P-1202 | Desalter | pressure | 365 d | 2026-08-08 | 2027-08-08 | 0.5% of span |
| PT-1202B | P-1202 | Desalter | pressure | 365 d | 2026-03-09 | 2027-03-09 | 0.5% of span |
| TT-1202 | P-1202 | Desalter | temperature | 365 d | 2026-06-17 | 2027-06-17 | 1.0 degC |
| VIB-1202 | P-1202 | Desalter | vibration | 180 d | 2026-06-19 | 2026-12-16 | 2.0% of reading |
| LT-1101 | TK-1101 | Crude Storage | level | 180 d | 2026-06-05 | 2026-12-02 | 0.5% of range |
| TT-1101 | TK-1101 | Crude Storage | temperature | 365 d | 2026-01-20 | 2027-01-20 | 1.0 degC |
| LT-1102 | TK-1102 | Crude Storage | level | 180 d | 2026-05-11 | 2026-11-07 | 0.5% of range |
| TT-1102 | TK-1102 | Crude Storage | temperature | 365 d | 2026-01-25 | 2027-01-25 | 1.0 degC |
| LT-1121 | TK-1121 | Product Storage | level | 180 d | 2026-08-19 | 2027-02-15 | 0.5% of range |
| TT-1121 | TK-1121 | Product Storage | temperature | 365 d | 2025-11-15 | 2026-11-15 | 1.0 degC |
| LT-1122 | TK-1122 | Product Storage | level | 180 d | 2026-05-19 | 2026-11-15 | 0.5% of range |
| TT-1122 | TK-1122 | Product Storage | temperature | 365 d | 2026-01-21 | 2027-01-21 | 1.0 degC |
| LT-1123 | TK-1123 | Product Storage | level | 180 d | 2026-04-12 | 2026-10-09 | 0.5% of range |
| TT-1123 | TK-1123 | Product Storage | temperature | 365 d | 2025-10-26 | 2026-10-26 | 1.0 degC |
| FT-1133 | UT-1133 | Cooling Water | flow | 365 d | 2026-07-28 | 2027-07-28 | 1.0% of rate |
| FT-1151 | UT-1151 | Utilities | flow | 365 d | 2026-08-16 | 2027-08-16 | 1.0% of rate |
| FT-1161 | UT-1161 | Flare | flow | 365 d | 2026-01-27 | 2027-01-27 | 1.0% of rate |
| PT-1003 | V-1003 | Crude Receiving | pressure | 365 d | 2026-09-05 | 2027-09-05 | 0.5% of span |
| ZT-1003 | V-1003 | Crude Receiving | position | 365 d | 2026-06-08 | 2027-06-08 | 1.0% of travel |
| PT-1047 | V-1047 | Crude Distillation | pressure | 365 d | 2025-10-20 | 2026-10-20 | 0.5% of span |
| ZT-1047 | V-1047 | Crude Distillation | position | 365 d | 2025-12-04 | 2026-12-04 | 1.0% of travel |
| PT-1064 | V-1064 | Naphtha Hydrotreater | pressure | 365 d | 2026-02-05 | 2027-02-05 | 0.5% of span |
| ZT-1064 | V-1064 | Naphtha Hydrotreater | position | 365 d | 2026-09-19 | 2027-09-19 | 1.0% of travel |
| PT-1103 | V-1103 | Crude Storage | pressure | 365 d | 2026-04-22 | 2027-04-22 | 0.5% of span |
| ZT-1103 | V-1103 | Crude Storage | position | 365 d | 2025-10-24 | 2026-10-24 | 1.0% of travel |
| PT-1203 | V-1203 | Desalter | pressure | 365 d | 2026-06-02 | 2027-06-02 | 0.5% of span |
| ZT-1203 | V-1203 | Desalter | position | 365 d | 2026-07-01 | 2027-07-01 | 1.0% of travel |
| LT-1046 | VS-1046 | Crude Distillation | level | 180 d | 2026-09-24 | 2027-03-23 | 0.5% of range |
| PT-1046 | VS-1046 | Crude Distillation | pressure | 365 d | 2025-12-27 | 2026-12-27 | 0.5% of span |
| TT-1046 | VS-1046 | Crude Distillation | temperature | 365 d | 2025-11-30 | 2026-11-30 | 1.0 degC |
| LT-1062 | VS-1062 | Naphtha Hydrotreater | level | 180 d | 2026-08-13 | 2027-02-09 | 0.5% of range |
| PT-1062 | VS-1062 | Naphtha Hydrotreater | pressure | 365 d | 2026-07-01 | 2027-07-01 | 0.5% of span |
| TT-1062 | VS-1062 | Naphtha Hydrotreater | temperature | 365 d | 2025-11-15 | 2026-11-15 | 1.0 degC |
| LT-1073 | VS-1073 | Catalytic Reforming | level | 180 d | 2026-08-14 | 2027-02-10 | 0.5% of range |
| PT-1073 | VS-1073 | Catalytic Reforming | pressure | 365 d | 2026-02-20 | 2027-02-20 | 0.5% of span |
| TT-1073 | VS-1073 | Catalytic Reforming | temperature | 365 d | 2026-04-07 | 2027-04-07 | 1.0 degC |
| LT-1081 | VS-1081 | FCC | level | 180 d | 2026-05-21 | 2026-11-17 | 0.5% of range |
| PT-1081 | VS-1081 | FCC | pressure | 365 d | 2026-01-17 | 2027-01-17 | 0.5% of span |
| TT-1081 | VS-1081 | FCC | temperature | 365 d | 2026-09-16 | 2027-09-16 | 1.0 degC |
| LT-1092 | VS-1092 | Diesel Hydrotreater | level | 180 d | 2026-09-21 | 2027-03-20 | 0.5% of range |
| PT-1092 | VS-1092 | Diesel Hydrotreater | pressure | 365 d | 2025-11-29 | 2026-11-29 | 0.5% of span |
| TT-1092 | VS-1092 | Diesel Hydrotreater | temperature | 365 d | 2026-05-31 | 2027-05-31 | 1.0 degC |
| LT-1113 | VS-1113 | Hydrogen | level | 180 d | 2026-06-07 | 2026-12-04 | 0.5% of range |
| PT-1113 | VS-1113 | Hydrogen | pressure | 365 d | 2026-09-05 | 2027-09-05 | 0.5% of span |
| TT-1113 | VS-1113 | Hydrogen | temperature | 365 d | 2026-03-27 | 2027-03-27 | 1.0 degC |
| LT-1126 | VS-1126 | Sulfur Recovery | level | 180 d | 2026-07-05 | 2027-01-01 | 0.5% of range |
| PT-1126 | VS-1126 | Sulfur Recovery | pressure | 365 d | 2026-05-24 | 2027-05-24 | 0.5% of span |
| TT-1126 | VS-1126 | Sulfur Recovery | temperature | 365 d | 2026-01-18 | 2027-01-18 | 1.0 degC |
| LT-1162 | VS-1162 | Flare | level | 180 d | 2026-05-15 | 2026-11-11 | 0.5% of range |
| PT-1162 | VS-1162 | Flare | pressure | 365 d | 2025-12-08 | 2026-12-08 | 0.5% of span |
| TT-1162 | VS-1162 | Flare | temperature | 365 d | 2026-08-01 | 2027-08-01 | 1.0 degC |
| LT-1172 | VS-1172 | Wastewater | level | 180 d | 2026-08-06 | 2027-02-02 | 0.5% of range |
| PT-1172 | VS-1172 | Wastewater | pressure | 365 d | 2026-01-01 | 2027-01-01 | 0.5% of span |
| TT-1172 | VS-1172 | Wastewater | temperature | 365 d | 2026-09-17 | 2027-09-17 | 1.0 degC |
| LT-1201 | VS-1201 | Desalter | level | 180 d | 2026-06-03 | 2026-11-30 | 0.5% of range |
| PT-1201 | VS-1201 | Desalter | pressure | 365 d | 2026-08-16 | 2027-08-16 | 0.5% of span |
| TT-1201 | VS-1201 | Desalter | temperature | 365 d | 2025-12-05 | 2026-12-05 | 1.0 degC |

### 5.5 Instrumentation notes

* Coverage of the compressor trains is the densest in the plant: the six registered compressors carry suction and discharge pressure, one or two temperature points, overall vibration and, on C-1071, a speed channel. This is deliberate - surge and bearing degradation are the two credible failure paths and both are observable.
* The seven-instrument pump blocks (P-1001, P-1202, P-1042, P-1051, P-1061, P-1084, P-1091, P-1124, P-1127, P-1131, P-1132, P-1142, P-1171) carry redundant pressure (A/B), flow, temperature, vibration, current and power. The A/B pressure pair is what allows SOP-14.2 to be executed without stopping the pump when one transmitter fails.
* Vibration channels use a rolling baseline rather than a fixed limit; the band shown in the table is the alarm envelope, and the learned baseline is evaluated separately (SOP-07.3 rev4).
* Position feedback is instrumented on the five registered valves; the position loop is the first place an actuator fault becomes visible.

## 6. Operating Parameters

This section states the operating envelope area by area. The `normal` band is the control target range; the plant is expected to run inside it. The `warning` band is the first deviation state and triggers increased monitoring. The `critical` band is the trip or immediate-action envelope. All figures are read from the register's own sensor definitions.

### 6.1 Crude Receiving

Controlling parameters for 4 units / 19 instruments. Receive tanker and pipeline crude and pump it to storage.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1001 | pressure (PT-1001A) | 20.35 bar | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| P-1001 | pressure (PT-1001B) | 20.35 bar | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| P-1001 | flow (FT-1001) | 105.6 m³/h | 101.38 .. 109.82 | 95.04 .. 114.05 | 86.59 .. 122.5 |
| P-1001 | temperature (TT-1001) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1001 | vibration (VIB-1001) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1001 | current (A-1001) | 92.4 A | 88.7 .. 96.1 | 83.16 .. 99.79 | 75.77 .. 107.18 |
| P-1001 | power (KW-1001) | 451 kW | 432.96 .. 469.04 | 405.9 .. 487.08 | 369.82 .. 523.16 |
| P-1002 | pressure (PT-1002A) | 20.35 bar | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| P-1002 | pressure (PT-1002B) | 20.35 bar | 19.54 .. 21.16 | 18.32 .. 21.98 | 16.69 .. 23.61 |
| P-1002 | flow (FT-1002) | 105.6 m³/h | 101.38 .. 109.82 | 95.04 .. 114.05 | 86.59 .. 122.5 |
| P-1002 | temperature (TT-1002) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1002 | vibration (VIB-1002) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1002 | current (A-1002) | 92.4 A | 88.7 .. 96.1 | 83.16 .. 99.79 | 75.77 .. 107.18 |
| P-1002 | power (KW-1002) | 451 kW | 432.96 .. 469.04 | 405.9 .. 487.08 | 369.82 .. 523.16 |
| V-1003 | position (ZT-1003) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| V-1003 | pressure (PT-1003) | 14.5 bar | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |
| E-1004 | temperature (TT-1004I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1004 | temperature (TT-1004O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1004 | flow (FT-1004) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |

Envelope note. The controlling measurement in this area is pressure on PT-1002A; the widest envelope is vibration on VIB-1001 and the tightest is pressure on PT-1001A. **Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

### 6.2 Crude Storage

Controlling parameters for 3 units / 6 instruments. Hold crude inventory and feed the desalter at a controlled rate.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| TK-1101 | level (LT-1101) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TK-1101 | temperature (TT-1101) | 41 °C | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| TK-1102 | level (LT-1102) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TK-1102 | temperature (TT-1102) | 41 °C | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| V-1103 | position (ZT-1103) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| V-1103 | pressure (PT-1103) | 14.5 bar | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |

Envelope note. The controlling measurement in this area is level on LT-1102; the widest envelope is temperature on TT-1101 and the tightest is level on LT-1101. **Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

### 6.3 Desalter

Controlling parameters for 3 units / 12 instruments. Remove salts and water from crude ahead of distillation.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| VS-1201 | pressure (PT-1201) | 9.5 bar | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| VS-1201 | temperature (TT-1201) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| VS-1201 | level (LT-1201) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| P-1202 | pressure (PT-1202A) | 11.1 bar | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| P-1202 | pressure (PT-1202B) | 11.1 bar | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| P-1202 | flow (FT-1202) | 57.6 m³/h | 55.3 .. 59.9 | 51.84 .. 62.21 | 47.23 .. 66.82 |
| P-1202 | temperature (TT-1202) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1202 | vibration (VIB-1202) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1202 | current (A-1202) | 50.4 A | 48.38 .. 52.42 | 45.36 .. 54.43 | 41.33 .. 58.46 |
| P-1202 | power (KW-1202) | 246 kW | 236.16 .. 255.84 | 221.4 .. 265.68 | 201.72 .. 285.36 |
| V-1203 | position (ZT-1203) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| V-1203 | pressure (PT-1203) | 14.5 bar | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |

Envelope note. The controlling measurement in this area is pressure on PT-1202A; the widest envelope is vibration on VIB-1202 and the tightest is pressure on PT-1202A. **Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

### 6.4 Crude Distillation

Controlling parameters for 6 units / 21 instruments. Split desalted crude into naphtha, kerosene, diesel and atmospheric residue.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1042 | pressure (PT-1042A) | 18.5 bar | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| P-1042 | pressure (PT-1042B) | 18.5 bar | 17.76 .. 19.24 | 16.65 .. 19.98 | 15.17 .. 21.46 |
| P-1042 | flow (FT-1042) | 96 m³/h | 92.16 .. 99.84 | 86.4 .. 103.68 | 78.72 .. 111.36 |
| P-1042 | temperature (TT-1042) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1042 | vibration (VIB-1042) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1042 | current (A-1042) | 84 A | 80.64 .. 87.36 | 75.6 .. 90.72 | 68.88 .. 97.44 |
| P-1042 | power (KW-1042) | 410 kW | 393.6 .. 426.4 | 369 .. 442.8 | 336.2 .. 475.6 |
| F-1043 | temperature (TT-1043) | 620 °C | 595.2 .. 644.8 | 558 .. 669.6 | 508.4 .. 719.2 |
| F-1043 | pressure (PT-1043) | 3.4 bar | 3.26 .. 3.54 | 3.06 .. 3.67 | 2.79 .. 3.94 |
| F-1043 | gas (GD-1043) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| COL-1044 | pressure (PT-1044) | 9.5 bar | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| COL-1044 | temperature (TT-1044) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| COL-1044 | level (LT-1044) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| E-1045 | temperature (TT-1045I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1045 | temperature (TT-1045O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1045 | flow (FT-1045) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| VS-1046 | pressure (PT-1046) | 7.6 bar | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| VS-1046 | temperature (TT-1046) | 150.4 °C | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| VS-1046 | level (LT-1046) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| V-1047 | position (ZT-1047) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| V-1047 | pressure (PT-1047) | 14.5 bar | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |

Envelope note. The controlling measurement in this area is pressure on PT-1042A; the widest envelope is gas on GD-1043 and the tightest is pressure on PT-1046. **Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

### 6.5 Vacuum Distillation

Controlling parameters for 4 units / 18 instruments. Recover vacuum gasoil from atmospheric residue under vacuum.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1051 | pressure (PT-1051A) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1051 | pressure (PT-1051B) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1051 | flow (FT-1051) | 86.4 m³/h | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| P-1051 | temperature (TT-1051) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1051 | vibration (VIB-1051) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1051 | current (A-1051) | 75.6 A | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| P-1051 | power (KW-1051) | 369 kW | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| COL-1052 | pressure (PT-1052) | 9.5 bar | 9.12 .. 9.88 | 8.55 .. 10.26 | 7.79 .. 11.02 |
| COL-1052 | temperature (TT-1052) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| COL-1052 | level (LT-1052) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| C-1053 | pressure (PT-1053S) | 4.76 bar | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| C-1053 | pressure (PT-1053D) | 13.65 bar | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| C-1053 | vibration (VIB-1053) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1053 | rpm (RPM-1053) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1053 | temperature (TT-1053) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| E-1054 | temperature (TT-1054I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1054 | temperature (TT-1054O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1054 | flow (FT-1054) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |

Envelope note. The controlling measurement in this area is pressure on PT-1052; the widest envelope is vibration on VIB-1051 and the tightest is pressure on PT-1053S. **Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

### 6.6 Naphtha Hydrotreater

Controlling parameters for 4 units / 15 instruments. Hydrotreat naphtha to remove sulphur and nitrogen ahead of reforming.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1061 | pressure (PT-1061A) | 14.8 bar | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| P-1061 | pressure (PT-1061B) | 14.8 bar | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| P-1061 | flow (FT-1061) | 76.8 m³/h | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| P-1061 | temperature (TT-1061) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1061 | vibration (VIB-1061) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1061 | current (A-1061) | 67.2 A | 64.51 .. 69.89 | 60.48 .. 72.58 | 55.1 .. 77.95 |
| P-1061 | power (KW-1061) | 328 kW | 314.88 .. 341.12 | 295.2 .. 354.24 | 268.96 .. 380.48 |
| VS-1062 | pressure (PT-1062) | 11.4 bar | 10.94 .. 11.86 | 10.26 .. 12.31 | 9.35 .. 13.22 |
| VS-1062 | temperature (TT-1062) | 225.6 °C | 216.58 .. 234.62 | 203.04 .. 243.65 | 184.99 .. 261.7 |
| VS-1062 | level (LT-1062) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| E-1063 | temperature (TT-1063I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1063 | temperature (TT-1063O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1063 | flow (FT-1063) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| V-1064 | position (ZT-1064) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| V-1064 | pressure (PT-1064) | 14.5 bar | 13.92 .. 15.08 | 13.05 .. 15.66 | 11.89 .. 16.82 |

Envelope note. The controlling measurement in this area is pressure on PT-1062; the widest envelope is vibration on VIB-1061 and the tightest is pressure on PT-1061A. **Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

### 6.7 Catalytic Reforming

Controlling parameters for 3 units / 11 instruments. Raise naphtha octane and produce reformate and hydrogen-rich gas.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| C-1071 | pressure (PT-1071S) | 6.8 bar | 6.53 .. 7.07 | 6.12 .. 7.34 | 5.58 .. 7.89 |
| C-1071 | pressure (PT-1071D) | 19.5 bar | 18.72 .. 20.28 | 17.55 .. 21.06 | 15.99 .. 22.62 |
| C-1071 | vibration (VIB-1071) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1071 | rpm (RPM-1071) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1071 | temperature (TT-1071) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| F-1072 | temperature (TT-1072) | 558 °C | 535.68 .. 580.32 | 502.2 .. 602.64 | 457.56 .. 647.28 |
| F-1072 | pressure (PT-1072) | 3.06 bar | 2.94 .. 3.18 | 2.75 .. 3.3 | 2.51 .. 3.55 |
| F-1072 | gas (GD-1072) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| VS-1073 | pressure (PT-1073) | 7.6 bar | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| VS-1073 | temperature (TT-1073) | 150.4 °C | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| VS-1073 | level (LT-1073) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |

Envelope note. The controlling measurement in this area is temperature on TT-1072; the widest envelope is gas on GD-1072 and the tightest is pressure on PT-1072. **Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

### 6.8 FCC

Controlling parameters for 4 units / 18 instruments. Crack vacuum gasoil to gasoline-range products and light gases.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| VS-1081 | pressure (PT-1081) | 13.3 bar | 12.77 .. 13.83 | 11.97 .. 14.36 | 10.91 .. 15.43 |
| VS-1081 | temperature (TT-1081) | 263.2 °C | 252.67 .. 273.73 | 236.88 .. 284.26 | 215.82 .. 305.31 |
| VS-1081 | level (LT-1081) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| C-1082 | pressure (PT-1082S) | 8.84 bar | 8.49 .. 9.19 | 7.96 .. 9.55 | 7.25 .. 10.25 |
| C-1082 | pressure (PT-1082D) | 25.35 bar | 24.34 .. 26.36 | 22.82 .. 27.38 | 20.79 .. 29.41 |
| C-1082 | vibration (VIB-1082) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1082 | rpm (RPM-1082) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1082 | temperature (TT-1082) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| E-1083 | temperature (TT-1083I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1083 | temperature (TT-1083O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1083 | flow (FT-1083) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |
| P-1084 | pressure (PT-1084A) | 22.2 bar | 21.31 .. 23.09 | 19.98 .. 23.98 | 18.2 .. 25.75 |
| P-1084 | pressure (PT-1084B) | 22.2 bar | 21.31 .. 23.09 | 19.98 .. 23.98 | 18.2 .. 25.75 |
| P-1084 | flow (FT-1084) | 115.2 m³/h | 110.59 .. 119.81 | 103.68 .. 124.42 | 94.46 .. 133.63 |
| P-1084 | temperature (TT-1084) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1084 | vibration (VIB-1084) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1084 | current (A-1084) | 100.8 A | 96.77 .. 104.83 | 90.72 .. 108.86 | 82.66 .. 116.93 |
| P-1084 | power (KW-1084) | 492 kW | 472.32 .. 511.68 | 442.8 .. 531.36 | 403.44 .. 570.72 |

Envelope note. The controlling measurement in this area is pressure on PT-1082S; the widest envelope is vibration on VIB-1082 and the tightest is pressure on PT-1082S. **FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

### 6.9 Diesel Hydrotreater

Controlling parameters for 3 units / 13 instruments. Hydrodesulphurise diesel to product specification.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1091 | pressure (PT-1091A) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1091 | pressure (PT-1091B) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1091 | flow (FT-1091) | 86.4 m³/h | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| P-1091 | temperature (TT-1091) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1091 | vibration (VIB-1091) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1091 | current (A-1091) | 75.6 A | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| P-1091 | power (KW-1091) | 369 kW | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| VS-1092 | pressure (PT-1092) | 10.45 bar | 10.03 .. 10.87 | 9.41 .. 11.29 | 8.57 .. 12.12 |
| VS-1092 | temperature (TT-1092) | 206.8 °C | 198.53 .. 215.07 | 186.12 .. 223.34 | 169.58 .. 239.89 |
| VS-1092 | level (LT-1092) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| E-1093 | temperature (TT-1093I) | 210 °C | 201.6 .. 218.4 | 189 .. 226.8 | 172.2 .. 243.6 |
| E-1093 | temperature (TT-1093O) | 188 °C | 180.48 .. 195.52 | 169.2 .. 203.04 | 154.16 .. 218.08 |
| E-1093 | flow (FT-1093) | 88 m³/h | 84.48 .. 91.52 | 79.2 .. 95.04 | 72.16 .. 102.08 |

Envelope note. The controlling measurement in this area is pressure on PT-1092; the widest envelope is vibration on VIB-1091 and the tightest is current on A-1091. **Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

### 6.10 Sulfur Recovery

Controlling parameters for 3 units / 15 instruments. Recover elemental sulphur from amine acid gas.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| C-1125 | pressure (PT-1125S) | 4.76 bar | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| C-1125 | pressure (PT-1125D) | 13.65 bar | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| C-1125 | vibration (VIB-1125) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1125 | rpm (RPM-1125) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1125 | temperature (TT-1125) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VS-1126 | pressure (PT-1126) | 7.6 bar | 7.3 .. 7.9 | 6.84 .. 8.21 | 6.23 .. 8.82 |
| VS-1126 | temperature (TT-1126) | 150.4 °C | 144.38 .. 156.42 | 135.36 .. 162.43 | 123.33 .. 174.46 |
| VS-1126 | level (LT-1126) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |
| P-1127 | pressure (PT-1127A) | 11.1 bar | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| P-1127 | pressure (PT-1127B) | 11.1 bar | 10.66 .. 11.54 | 9.99 .. 11.99 | 9.1 .. 12.88 |
| P-1127 | flow (FT-1127) | 57.6 m³/h | 55.3 .. 59.9 | 51.84 .. 62.21 | 47.23 .. 66.82 |
| P-1127 | temperature (TT-1127) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1127 | vibration (VIB-1127) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1127 | current (A-1127) | 50.4 A | 48.38 .. 52.42 | 45.36 .. 54.43 | 41.33 .. 58.46 |
| P-1127 | power (KW-1127) | 246 kW | 236.16 .. 255.84 | 221.4 .. 265.68 | 201.72 .. 285.36 |

Envelope note. The controlling measurement in this area is pressure on PT-1125S; the widest envelope is vibration on VIB-1125 and the tightest is pressure on PT-1126. **Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

### 6.11 Hydrogen

Controlling parameters for 3 units / 11 instruments. Generate and purify hydrogen for the hydrotreaters.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| F-1111 | temperature (TT-1111) | 682 °C | 654.72 .. 709.28 | 613.8 .. 736.56 | 559.24 .. 791.12 |
| F-1111 | pressure (PT-1111) | 3.74 bar | 3.59 .. 3.89 | 3.37 .. 4.04 | 3.07 .. 4.34 |
| F-1111 | gas (GD-1111) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| C-1112 | pressure (PT-1112S) | 6.12 bar | 5.88 .. 6.36 | 5.51 .. 6.61 | 5.02 .. 7.1 |
| C-1112 | pressure (PT-1112D) | 17.55 bar | 16.85 .. 18.25 | 15.8 .. 18.95 | 14.39 .. 20.36 |
| C-1112 | vibration (VIB-1112) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1112 | rpm (RPM-1112) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1112 | temperature (TT-1112) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |
| VS-1113 | pressure (PT-1113) | 6.65 bar | 6.38 .. 6.92 | 5.98 .. 7.18 | 5.45 .. 7.71 |
| VS-1113 | temperature (TT-1113) | 131.6 °C | 126.34 .. 136.86 | 118.44 .. 142.13 | 107.91 .. 152.66 |
| VS-1113 | level (LT-1113) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |

Envelope note. The controlling measurement in this area is pressure on PT-1112S; the widest envelope is gas on GD-1111 and the tightest is pressure on PT-1112S. **Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

### 6.12 Product Storage

Controlling parameters for 4 units / 13 instruments. Hold finished naphtha, diesel and jet and load out product.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| TK-1121 | level (LT-1121) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TK-1121 | temperature (TT-1121) | 41 °C | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| TK-1122 | level (LT-1122) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TK-1122 | temperature (TT-1122) | 41 °C | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| TK-1123 | level (LT-1123) | 62 % | 59.52 .. 64.48 | 55.8 .. 66.96 | 50.84 .. 71.92 |
| TK-1123 | temperature (TT-1123) | 41 °C | 39.36 .. 42.64 | 36.9 .. 44.28 | 33.62 .. 47.56 |
| P-1124 | pressure (PT-1124A) | 14.8 bar | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| P-1124 | pressure (PT-1124B) | 14.8 bar | 14.21 .. 15.39 | 13.32 .. 15.98 | 12.14 .. 17.17 |
| P-1124 | flow (FT-1124) | 76.8 m³/h | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| P-1124 | temperature (TT-1124) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1124 | vibration (VIB-1124) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1124 | current (A-1124) | 67.2 A | 64.51 .. 69.89 | 60.48 .. 72.58 | 55.1 .. 77.95 |
| P-1124 | power (KW-1124) | 328 kW | 314.88 .. 341.12 | 295.2 .. 354.24 | 268.96 .. 380.48 |

Envelope note. The controlling measurement in this area is level on LT-1122; the widest envelope is vibration on VIB-1124 and the tightest is pressure on PT-1124A. **Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

### 6.13 Utilities

Controlling parameters for 2 units / 6 instruments. Supply instrument air and plant air to the whole site.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| UT-1151 | flow (FT-1151) | 96 m³/h | 92.16 .. 99.84 | 86.4 .. 103.68 | 78.72 .. 111.36 |
| C-1152 | pressure (PT-1152S) | 4.76 bar | 4.57 .. 4.95 | 4.28 .. 5.14 | 3.9 .. 5.52 |
| C-1152 | pressure (PT-1152D) | 13.65 bar | 13.1 .. 14.2 | 12.28 .. 14.74 | 11.19 .. 15.83 |
| C-1152 | vibration (VIB-1152) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| C-1152 | rpm (RPM-1152) | 8840 rpm | 8486.4 .. 9193.6 | 7956 .. 9547.2 | 7248.8 .. 10254.4 |
| C-1152 | temperature (TT-1152) | 79 °C | 75.84 .. 82.16 | 71.1 .. 85.32 | 64.78 .. 91.64 |

Envelope note. The controlling measurement in this area is pressure on PT-1152S; the widest envelope is vibration on VIB-1152 and the tightest is pressure on PT-1152S. **Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

### 6.14 Steam

Controlling parameters for 3 units / 13 instruments. Raise and distribute steam and return boiler feed water.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| F-1141 | temperature (TT-1141) | 620 °C | 595.2 .. 644.8 | 558 .. 669.6 | 508.4 .. 719.2 |
| F-1141 | pressure (PT-1141) | 3.4 bar | 3.26 .. 3.54 | 3.06 .. 3.67 | 2.79 .. 3.94 |
| F-1141 | gas (GD-1141) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| P-1142 | pressure (PT-1142A) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1142 | pressure (PT-1142B) | 16.65 bar | 15.98 .. 17.32 | 14.99 .. 17.98 | 13.65 .. 19.31 |
| P-1142 | flow (FT-1142) | 86.4 m³/h | 82.94 .. 89.86 | 77.76 .. 93.31 | 70.85 .. 100.22 |
| P-1142 | temperature (TT-1142) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1142 | vibration (VIB-1142) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1142 | current (A-1142) | 75.6 A | 72.58 .. 78.62 | 68.04 .. 81.65 | 61.99 .. 87.7 |
| P-1142 | power (KW-1142) | 369 kW | 354.24 .. 383.76 | 332.1 .. 398.52 | 302.58 .. 428.04 |
| M-1143 | current (A-1143) | 76.8 A | 73.73 .. 79.87 | 69.12 .. 82.94 | 62.98 .. 89.09 |
| M-1143 | power (KW-1143) | 368 kW | 353.28 .. 382.72 | 331.2 .. 397.44 | 301.76 .. 426.88 |
| M-1143 | rpm (RPM-1143) | 1480 rpm | 1420.8 .. 1539.2 | 1332 .. 1598.4 | 1213.6 .. 1716.8 |

Envelope note. The controlling measurement in this area is pressure on PT-1142A; the widest envelope is gas on GD-1141 and the tightest is current on A-1142. **Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

### 6.15 Cooling Water

Controlling parameters for 3 units / 15 instruments. Reject process heat to atmosphere and circulate cooling water.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1131 | pressure (PT-1131A) | 24.05 bar | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| P-1131 | pressure (PT-1131B) | 24.05 bar | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| P-1131 | flow (FT-1131) | 124.8 m³/h | 119.81 .. 129.79 | 112.32 .. 134.78 | 102.34 .. 144.77 |
| P-1131 | temperature (TT-1131) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1131 | vibration (VIB-1131) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1131 | current (A-1131) | 109.2 A | 104.83 .. 113.57 | 98.28 .. 117.94 | 89.54 .. 126.67 |
| P-1131 | power (KW-1131) | 533 kW | 511.68 .. 554.32 | 479.7 .. 575.64 | 437.06 .. 618.28 |
| P-1132 | pressure (PT-1132A) | 24.05 bar | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| P-1132 | pressure (PT-1132B) | 24.05 bar | 23.09 .. 25.01 | 21.64 .. 25.97 | 19.72 .. 27.9 |
| P-1132 | flow (FT-1132) | 124.8 m³/h | 119.81 .. 129.79 | 112.32 .. 134.78 | 102.34 .. 144.77 |
| P-1132 | temperature (TT-1132) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1132 | vibration (VIB-1132) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1132 | current (A-1132) | 109.2 A | 104.83 .. 113.57 | 98.28 .. 117.94 | 89.54 .. 126.67 |
| P-1132 | power (KW-1132) | 533 kW | 511.68 .. 554.32 | 479.7 .. 575.64 | 437.06 .. 618.28 |
| UT-1133 | flow (FT-1133) | 144 m³/h | 138.24 .. 149.76 | 129.6 .. 155.52 | 118.08 .. 167.04 |

Envelope note. The controlling measurement in this area is pressure on PT-1132A; the widest envelope is vibration on VIB-1131 and the tightest is pressure on PT-1131A. **Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

### 6.16 Flare

Controlling parameters for 2 units / 4 instruments. Safely dispose of relief and upset hydrocarbon vapour.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| UT-1161 | flow (FT-1161) | 48 m³/h | 46.08 .. 49.92 | 43.2 .. 51.84 | 39.36 .. 55.68 |
| VS-1162 | pressure (PT-1162) | 4.75 bar | 4.56 .. 4.94 | 4.28 .. 5.13 | 3.89 .. 5.51 |
| VS-1162 | temperature (TT-1162) | 94 °C | 90.24 .. 97.76 | 84.6 .. 101.52 | 77.08 .. 109.04 |
| VS-1162 | level (LT-1162) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |

Envelope note. The controlling measurement in this area is pressure on PT-1162; the widest envelope is pressure on PT-1162 and the tightest is flow on FT-1161. **Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

### 6.17 Wastewater

Controlling parameters for 2 units / 10 instruments. Separate oil from process water before discharge.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| P-1171 | pressure (PT-1171A) | 9.25 bar | 8.88 .. 9.62 | 8.33 .. 9.99 | 7.58 .. 10.73 |
| P-1171 | pressure (PT-1171B) | 9.25 bar | 8.88 .. 9.62 | 8.33 .. 9.99 | 7.58 .. 10.73 |
| P-1171 | flow (FT-1171) | 48 m³/h | 46.08 .. 49.92 | 43.2 .. 51.84 | 39.36 .. 55.68 |
| P-1171 | temperature (TT-1171) | 73 °C | 70.08 .. 75.92 | 65.7 .. 78.84 | 59.86 .. 84.68 |
| P-1171 | vibration (VIB-1171) | 5.7 mm/s | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| P-1171 | current (A-1171) | 42 A | 40.32 .. 43.68 | 37.8 .. 45.36 | 34.44 .. 48.72 |
| P-1171 | power (KW-1171) | 205 kW | 196.8 .. 213.2 | 184.5 .. 221.4 | 168.1 .. 237.8 |
| VS-1172 | pressure (PT-1172) | 5.7 bar | 5.47 .. 5.93 | 5.13 .. 6.16 | 4.67 .. 6.61 |
| VS-1172 | temperature (TT-1172) | 112.8 °C | 108.29 .. 117.31 | 101.52 .. 121.82 | 92.5 .. 130.85 |
| VS-1172 | level (LT-1172) | 55 % | 52.8 .. 57.2 | 49.5 .. 59.4 | 45.1 .. 63.8 |

Envelope note. The controlling measurement in this area is pressure on PT-1172; the widest envelope is vibration on VIB-1171 and the tightest is temperature on TT-1172. **Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

### 6.18 Safety Systems

Controlling parameters for 2 units / 4 instruments. Detect fire and gas and execute emergency shutdown.

| Asset | Parameter | Nominal | Normal band | Warning band | Critical band |
|---|---|---|---|---|---|
| ESD-1181 | gas (GD-1181) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| ESD-1181 | leak (LK-1181) | 0 0/1 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| ESD-1182 | gas (GD-1182) | 0 ppm | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |
| ESD-1182 | leak (LK-1182) | 0 0/1 | 0 .. 0.2 | 0.2 .. 0.5 | 0.5 .. 1 |

Envelope note. The controlling measurement in this area is gas on GD-1182; the widest envelope is gas on GD-1181 and the tightest is gas on GD-1181. **Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

## 7. Maintenance History

This section is the five-year maintenance history from 2021-06 through 2026-09. It is presented as five campaign years. The campaign years are deliberately not calendar years: they are the phases the reliability programme actually ran in, and they are bounded so that each required milestone falls in the right phase. The full event register follows the narrative.

| Campaign phase | Window | Theme |
|---|---|---|
| Year 1 | 2021-06-01 .. 2022-09-30 | Commissioning and baselining |
| Year 2 | 2022-10-01 .. 2024-02-28 | First minor vibration event |
| Year 3 | 2024-03-01 .. 2025-08-31 | Drive-end bearing replacement |
| Year 4 | 2025-09-01 .. 2026-05-31 | Rising vibration trend |
| Year 5 | 2026-06-01 .. 2026-09-30 | Current anomaly |

### 7.1 Year 1 - Commissioning and baselining

The review period opens with the compression train recommissioned after the rotor re-installation campaign. Baseline vibration on the drive-end bearing housing was established at **5.7 mm/s at 8,800 rpm** on 2021-06-14 and entered the condition-monitoring system as the learned baseline for the machine. That number is still the reference every later deviation is measured against. The same window delivered the current revision of the vibration response standard, SOP-07.3 rev4, and the first full instrument loop check across the seven-instrument pump blocks. Work in this year was overwhelmingly preventive: commissioning checks, loop verification, lubrication changes and baseline surveys.

Recorded in this phase: 70 maintenance events, of which 28 were corrective and 42 preventive.

### 7.2 Year 2 - First minor vibration event

The first minor vibration event appeared on 2022-11-18, when overall vibration briefly reached 6.1 mm/s on the drive-end housing during a lube-oil temperature excursion. The event cleared without mechanical intervention after a lube-oil flush and a filter change, but it established two things that shaped the rest of the record: the machine responds to oil condition before it responds to load, and the 1x component is the earliest indicator. The same year raised WO-2417, the coupling alignment inspection that would be re-executed three years later.

Recorded in this phase: 74 maintenance events, of which 34 were corrective and 40 preventive.

### 7.3 Year 3 - Drive-end bearing replacement

The drive-end bearing replacement of 2025-03-16 is the single most significant intervention in the record. Inspection IR-198 documents outer-race spalling on two rolling elements and lube-oil varnish on the cage; maintenance event ME-198 fitted an OEM spare and re-checked alignment before return to service. Post-repair overall vibration fell to 5.4 mm/s and the machine was re-baselined at 5.69 mm/s. The year also carried the first exchanger fouling review on E-340 and the tank integrity inspections on T-118.

Recorded in this phase: 78 maintenance events, of which 25 were corrective and 53 preventive.

### 7.4 Year 4 - Rising vibration trend

Vibration began climbing again, slowly and monotonically. The 90-day rolling mean moved 5.69 -> 5.74 -> 5.80 mm/s across the year, and a hot alignment check on 2025-11-02 (ME-212, re-executing WO-2417) measured a coupling offset of 0.06 mm against a 0.10 mm tolerance - inside tolerance, so no correction was made. Because alignment was eliminated as the driver, the residual trend was attributed to bearing degradation and placed under quarterly review.

Recorded in this phase: 40 maintenance events, of which 16 were corrective and 24 preventive.

### 7.5 Year 5 - Current anomaly

The current anomaly crystallised on 2026-09-06. The IR-204 vibration survey measured 6.8 mm/s on the drive-end bearing housing against the 5.8 mm/s 90-day rolling baseline, an 18% increase developed progressively over eight days rather than as a step change, with drive-end bearing temperature at 79 degC against a 68 degC baseline. Anomaly A-51 tracks it. Daily monitoring was imposed under SOP-07.3 rev4 section 4.2, WO-8852 was raised for drive-end bearing inspection and is pending outage approval APR-231. The machine remains on line inside its 7.1 mm/s alarm limit.

Recorded in this phase: 22 maintenance events, of which 8 were corrective and 14 preventive.

### 7.6 Maintenance event register

Every recorded event carries a maintenance event id (`ME-\d+`) and, where a work order was raised, a work order number (`WO-\d+`). The register is in strict date order. 284 events are recorded in the period.

| Date | ME id | WO | Equipment | Area | Type | Scope | Outcome |
|---|---|---|---|---|---|---|---|
| 2021-06-01 | ME-001 | WO-4100 | M-1143 | Steam | preventive | vibration and current survey | Check completed inside tolerance, next interval retained |
| 2021-06-08 | ME-002 | WO-4101 | V-1064 | Naphtha Hydrotreater | preventive | stroke test and position feedback calibration | Consumable renewed, condition confirmed normal |
| 2021-06-15 | ME-003 | WO-4102 | C-1053 | Vacuum Distillation | corrective | bearing temperature survey | Fault corrected, equipment returned to service inside the normal band |
| 2021-06-22 | ME-004 | WO-4103 | E-1045 | Crude Distillation | preventive | gasket and flange inspection | No findings, next inspection interval retained |
| 2021-06-29 | ME-005 | WO-4104 | V-1003 | Crude Receiving | preventive | packing replacement | Minor wear noted, no immediate action |
| 2021-07-06 | ME-006 | WO-4105 | P-1171 | Wastewater | preventive | bearing lubrication and vibration survey | No findings, next inspection interval retained |
| 2021-07-13 | ME-007 | WO-4106 | F-1141 | Steam | preventive | tube skin-temperature survey | No findings, next inspection interval retained |
| 2021-07-20 | ME-008 | WO-4107 | C-1112 | Hydrogen | preventive | lube-oil sampling and analysis | Consumable renewed, condition confirmed normal |
| 2021-07-27 | ME-009 | WO-4108 | F-1072 | Catalytic Reforming | corrective | refractory inspection | Component replaced, post-work survey inside the normal band |
| 2021-08-03 | ME-010 | WO-4109 | P-1091 | Diesel Hydrotreater | corrective | motor current signature test | Temporary repair applied, follow-up work order raised |
| 2021-08-10 | ME-011 | WO-4110 | P-1124 | Product Storage | corrective | bearing lubrication and vibration survey | Deviation cleared after adjustment, trend review scheduled |
| 2021-08-17 | ME-012 | WO-4111 | VS-1162 | Flare | preventive | level instrument calibration | Check completed inside tolerance, next interval retained |
| 2021-08-24 | ME-013 | WO-4112 | P-1061 | Naphtha Hydrotreater | preventive | coupling alignment check | No findings, next inspection interval retained |
| 2021-08-31 | ME-014 | WO-4113 | TK-1123 | Product Storage | preventive | secondary containment inspection | Check completed inside tolerance, next interval retained |
| 2021-09-07 | ME-015 | WO-4114 | TK-1101 | Crude Storage | preventive | internal floating roof check | No findings, next inspection interval retained |
| 2021-09-14 | ME-016 | WO-4115 | E-1054 | Vacuum Distillation | preventive | tube bundle eddy-current survey | No findings, next inspection interval retained |
| 2021-09-21 | ME-017 | WO-4116 | VS-1062 | Naphtha Hydrotreater | preventive | relief valve recertification | Consumable renewed, condition confirmed normal |
| 2021-09-28 | ME-018 | WO-4117 | M-1143 | Steam | preventive | winding insulation resistance test | Check completed inside tolerance, next interval retained |
| 2021-10-05 | ME-019 | WO-4118 | COL-1052 | Vacuum Distillation | preventive | reflux system inspection | Minor wear noted, no immediate action |
| 2021-10-12 | ME-020 | WO-4119 | P-1131 | Cooling Water | corrective | mechanical seal inspection | Component replaced, post-work survey inside the normal band |
| 2021-10-19 | ME-021 | WO-4120 | V-1103 | Crude Storage | corrective | packing replacement | Deviation cleared after adjustment, trend review scheduled |
| 2021-10-26 | ME-022 | WO-4121 | VS-1172 | Wastewater | preventive | relief valve recertification | Minor wear noted, no immediate action |
| 2021-11-02 | ME-023 | WO-4122 | P-1042 | Crude Distillation | corrective | coupling alignment check | Temporary repair applied, follow-up work order raised |
| 2021-11-09 | ME-024 | WO-4123 | UT-1133 | Cooling Water | preventive | control loop verification | Consumable renewed, condition confirmed normal |
| 2021-11-16 | ME-025 | WO-4124 | TK-1121 | Product Storage | preventive | internal floating roof check | Check completed inside tolerance, next interval retained |
| 2021-11-23 | ME-026 | WO-4125 | VS-1092 | Diesel Hydrotreater | preventive | wall-thickness survey | Minor wear noted, no immediate action |
| 2021-11-30 | ME-027 | WO-4126 | P-1124 | Product Storage | corrective | motor current signature test | Temporary repair applied, follow-up work order raised |
| 2021-12-07 | ME-028 | WO-4127 | UT-1161 | Flare | corrective | performance test | Deviation cleared after adjustment, trend review scheduled |
| 2021-12-14 | ME-029 | WO-4128 | P-1171 | Wastewater | preventive | suction strainer cleaning | Minor wear noted, no immediate action |
| 2021-12-21 | ME-030 | WO-4129 | F-1043 | Crude Distillation | preventive | draft and excess-oxygen survey | No findings, next inspection interval retained |
| 2021-12-28 | ME-031 | WO-4130 | E-1045 | Crude Distillation | preventive | delta-P trend review and cleaning assessment | Check completed inside tolerance, next interval retained |
| 2022-01-04 | ME-032 | WO-4700 | P-1084 | FCC | corrective | suction strainer cleaning | Temporary repair applied, follow-up work order raised |
| 2022-01-11 | ME-033 | WO-4701 | P-1001 | Crude Receiving | corrective | motor current signature test | Component replaced, post-work survey inside the normal band |
| 2022-01-18 | ME-034 | WO-4702 | C-1112 | Hydrogen | corrective | rotor alignment check | Deviation cleared after adjustment, trend review scheduled |
| 2022-01-25 | ME-035 | WO-4703 | TK-1102 | Crude Storage | corrective | secondary containment inspection | Deviation cleared after adjustment, trend review scheduled |
| 2022-02-01 | ME-036 | WO-4704 | P-1084 | FCC | corrective | coupling alignment check | Temporary repair applied, follow-up work order raised |
| 2022-02-08 | ME-037 | WO-4705 | TK-1122 | Product Storage | preventive | secondary containment inspection | Consumable renewed, condition confirmed normal |
| 2022-02-15 | ME-038 | WO-4706 | E-1083 | FCC | corrective | gasket and flange inspection | Fault corrected, equipment returned to service inside the normal band |
| 2022-02-22 | ME-039 | WO-4707 | UT-1133 | Cooling Water | preventive | control loop verification | Minor wear noted, no immediate action |
| 2022-03-01 | ME-040 | WO-4708 | F-1141 | Steam | preventive | tube skin-temperature survey | Consumable renewed, condition confirmed normal |
| 2022-03-08 | ME-041 | WO-4709 | VS-1062 | Naphtha Hydrotreater | preventive | wall-thickness survey | Minor wear noted, no immediate action |
| 2022-03-15 | ME-042 | WO-4710 | P-1002 | Crude Receiving | preventive | impeller wear check | Consumable renewed, condition confirmed normal |
| 2022-03-22 | ME-043 | WO-4711 | C-1152 | Utilities | corrective | anti-surge valve stroke test | Temporary repair applied, follow-up work order raised |
| 2022-03-29 | ME-044 | WO-4712 | TK-1122 | Product Storage | preventive | external visual inspection | Check completed inside tolerance, next interval retained |
| 2022-04-05 | ME-045 | WO-4713 | UT-1161 | Flare | corrective | control loop verification | Component replaced, post-work survey inside the normal band |
| 2022-04-12 | ME-046 | WO-4714 | VS-1126 | Sulfur Recovery | preventive | relief valve recertification | Check completed inside tolerance, next interval retained |
| 2022-04-19 | ME-047 | WO-4715 | VS-1081 | FCC | preventive | relief valve recertification | Consumable renewed, condition confirmed normal |
| 2022-04-26 | ME-048 | WO-4716 | COL-1052 | Vacuum Distillation | preventive | tray efficiency assessment | Check completed inside tolerance, next interval retained |
| 2022-05-03 | ME-049 | WO-4717 | E-1093 | Diesel Hydrotreater | preventive | shell-side flow verification | Minor wear noted, no immediate action |
| 2022-05-10 | ME-050 | WO-4718 | VS-1126 | Sulfur Recovery | corrective | relief valve recertification | Component replaced, post-work survey inside the normal band |
| 2022-05-17 | ME-051 | WO-4719 | VS-1201 | Desalter | preventive | internals inspection | No findings, next inspection interval retained |
| 2022-05-24 | ME-052 | WO-4720 | VS-1201 | Desalter | preventive | internals inspection | Consumable renewed, condition confirmed normal |
| 2022-05-31 | ME-053 | WO-4721 | P-1202 | Desalter | corrective | motor current signature test | Fault corrected, equipment returned to service inside the normal band |
| 2022-06-07 | ME-054 | WO-4722 | P-1042 | Crude Distillation | corrective | coupling alignment check | Deviation cleared after adjustment, trend review scheduled |
| 2022-06-14 | ME-055 | WO-2417 | C-1071 | Catalytic Reforming | preventive | coupling alignment inspection raised (legacy CMMS number) | No findings, next inspection interval retained |
| 2022-06-21 | ME-056 | WO-4723 | TK-1101 | Crude Storage | preventive | roof seal inspection | Check completed inside tolerance, next interval retained |
| 2022-06-28 | ME-057 | WO-4724 | ESD-1182 | Safety Systems | preventive | proof test | Check completed inside tolerance, next interval retained |
| 2022-07-05 | ME-058 | WO-4725 | UT-1161 | Flare | preventive | performance test | Consumable renewed, condition confirmed normal |
| 2022-07-12 | ME-059 | WO-4726 | TK-1102 | Crude Storage | corrective | external visual inspection | Component replaced, post-work survey inside the normal band |
| 2022-07-19 | ME-060 | WO-4727 | TK-1102 | Crude Storage | corrective | level transmitter calibration | Deviation cleared after adjustment, trend review scheduled |
| 2022-07-26 | ME-061 | WO-4728 | C-1125 | Sulfur Recovery | corrective | anti-surge valve stroke test | Deviation cleared after adjustment, trend review scheduled |
| 2022-08-02 | ME-062 | WO-4729 | VS-1126 | Sulfur Recovery | preventive | relief valve recertification | No findings, next inspection interval retained |
| 2022-08-09 | ME-063 | WO-4730 | P-1084 | FCC | corrective | motor current signature test | Temporary repair applied, follow-up work order raised |
| 2022-08-16 | ME-064 | WO-4731 | VS-1113 | Hydrogen | corrective | relief valve recertification | Component replaced, post-work survey inside the normal band |
| 2022-08-23 | ME-065 | WO-4732 | F-1043 | Crude Distillation | preventive | refractory inspection | Consumable renewed, condition confirmed normal |
| 2022-08-30 | ME-066 | WO-4733 | VS-1046 | Crude Distillation | corrective | internals inspection | Deviation cleared after adjustment, trend review scheduled |
| 2022-09-06 | ME-067 | WO-4734 | P-1202 | Desalter | preventive | mechanical seal inspection | Check completed inside tolerance, next interval retained |
| 2022-09-13 | ME-068 | WO-4735 | VS-1073 | Catalytic Reforming | corrective | relief valve recertification | Temporary repair applied, follow-up work order raised |
| 2022-09-20 | ME-069 | WO-4736 | P-1202 | Desalter | preventive | motor current signature test | Check completed inside tolerance, next interval retained |
| 2022-09-27 | ME-070 | WO-4737 | C-1125 | Sulfur Recovery | corrective | dry gas seal inspection | Deviation cleared after adjustment, trend review scheduled |
| 2022-10-04 | ME-071 | WO-4738 | COL-1052 | Vacuum Distillation | corrective | tray efficiency assessment | Temporary repair applied, follow-up work order raised |
| 2022-10-11 | ME-072 | WO-4739 | P-1124 | Product Storage | corrective | suction strainer cleaning | Temporary repair applied, follow-up work order raised |
| 2022-10-18 | ME-073 | WO-4740 | P-1132 | Cooling Water | corrective | motor current signature test | Fault corrected, equipment returned to service inside the normal band |
| 2022-10-25 | ME-074 | WO-4741 | P-1127 | Sulfur Recovery | corrective | impeller wear check | Component replaced, post-work survey inside the normal band |
| 2022-11-01 | ME-075 | WO-4742 | V-1047 | Crude Distillation | preventive | seat leakage check | Check completed inside tolerance, next interval retained |
| 2022-11-08 | ME-076 | WO-4743 | C-1125 | Sulfur Recovery | corrective | dry gas seal inspection | Component replaced, post-work survey inside the normal band |
| 2022-11-15 | ME-077 | WO-4744 | P-1127 | Sulfur Recovery | preventive | mechanical seal inspection | No findings, next inspection interval retained |
| 2022-11-22 | ME-078 | WO-4745 | C-1053 | Vacuum Distillation | corrective | bearing temperature survey | Component replaced, post-work survey inside the normal band |
| 2022-11-29 | ME-079 | WO-4746 | P-1091 | Diesel Hydrotreater | preventive | motor current signature test | Minor wear noted, no immediate action |
| 2022-12-06 | ME-080 | WO-4747 | P-1127 | Sulfur Recovery | preventive | coupling alignment check | Minor wear noted, no immediate action |
| 2022-12-13 | ME-081 | WO-4748 | P-1051 | Vacuum Distillation | corrective | bearing lubrication and vibration survey | Fault corrected, equipment returned to service inside the normal band |
| 2022-12-20 | ME-082 | WO-4749 | TK-1101 | Crude Storage | preventive | level transmitter calibration | Consumable renewed, condition confirmed normal |
| 2022-12-27 | ME-083 | WO-4750 | P-1091 | Diesel Hydrotreater | corrective | coupling alignment check | Temporary repair applied, follow-up work order raised |
| 2023-01-03 | ME-084 | WO-5200 | C-1112 | Hydrogen | preventive | anti-surge valve stroke test | Check completed inside tolerance, next interval retained |
| 2023-01-10 | ME-085 | WO-5201 | V-1203 | Desalter | corrective | actuator overhaul | Deviation cleared after adjustment, trend review scheduled |
| 2023-01-17 | ME-086 | WO-5202 | VS-1162 | Flare | preventive | level instrument calibration | Consumable renewed, condition confirmed normal |
| 2023-01-24 | ME-087 | WO-5203 | E-1045 | Crude Distillation | corrective | tube bundle eddy-current survey | Deviation cleared after adjustment, trend review scheduled |
| 2023-01-31 | ME-088 | WO-5204 | TK-1123 | Product Storage | corrective | secondary containment inspection | Temporary repair applied, follow-up work order raised |
| 2023-02-07 | ME-089 | WO-5205 | C-1152 | Utilities | preventive | surge margin check | Consumable renewed, condition confirmed normal |
| 2023-02-14 | ME-090 | WO-5206 | VS-1092 | Diesel Hydrotreater | corrective | internals inspection | Fault corrected, equipment returned to service inside the normal band |
| 2023-02-21 | ME-091 | WO-5207 | VS-1113 | Hydrogen | corrective | wall-thickness survey | Fault corrected, equipment returned to service inside the normal band |
| 2023-02-28 | ME-092 | WO-5208 | P-1131 | Cooling Water | preventive | bearing lubrication and vibration survey | Consumable renewed, condition confirmed normal |
| 2023-03-07 | ME-093 | WO-5209 | UT-1151 | Utilities | preventive | control loop verification | No findings, next inspection interval retained |
| 2023-03-14 | ME-094 | WO-5210 | ESD-1181 | Safety Systems | preventive | final element stroke test | No findings, next inspection interval retained |
| 2023-03-21 | ME-095 | WO-5211 | P-1127 | Sulfur Recovery | preventive | mechanical seal inspection | Minor wear noted, no immediate action |
| 2023-03-28 | ME-096 | WO-5212 | P-1202 | Desalter | corrective | mechanical seal inspection | Fault corrected, equipment returned to service inside the normal band |
| 2023-04-04 | ME-097 | WO-5213 | C-1152 | Utilities | preventive | dry gas seal inspection | Minor wear noted, no immediate action |
| 2023-04-11 | ME-098 | WO-5214 | VS-1081 | FCC | preventive | wall-thickness survey | Minor wear noted, no immediate action |
| 2023-04-18 | ME-099 | WO-5215 | P-1061 | Naphtha Hydrotreater | preventive | suction strainer cleaning | No findings, next inspection interval retained |
| 2023-04-25 | ME-100 | WO-5216 | V-1047 | Crude Distillation | preventive | packing replacement | Check completed inside tolerance, next interval retained |
| 2023-05-02 | ME-101 | WO-5217 | E-1004 | Crude Receiving | preventive | shell-side flow verification | No findings, next inspection interval retained |
| 2023-05-09 | ME-102 | WO-5218 | P-1002 | Crude Receiving | corrective | coupling alignment check | Component replaced, post-work survey inside the normal band |
| 2023-05-16 | ME-103 | WO-5219 | E-1083 | FCC | corrective | delta-P trend review and cleaning assessment | Component replaced, post-work survey inside the normal band |
| 2023-05-23 | ME-104 | WO-5220 | UT-1161 | Flare | corrective | control loop verification | Deviation cleared after adjustment, trend review scheduled |
| 2023-05-30 | ME-105 | WO-5221 | P-1127 | Sulfur Recovery | corrective | suction strainer cleaning | Deviation cleared after adjustment, trend review scheduled |
| 2023-06-06 | ME-106 | WO-5222 | C-1053 | Vacuum Distillation | corrective | lube-oil sampling and analysis | Deviation cleared after adjustment, trend review scheduled |
| 2023-06-13 | ME-107 | WO-5223 | VS-1113 | Hydrogen | corrective | level instrument calibration | Fault corrected, equipment returned to service inside the normal band |
| 2023-06-20 | ME-108 | WO-5224 | E-1045 | Crude Distillation | preventive | shell-side flow verification | No findings, next inspection interval retained |
| 2023-06-27 | ME-109 | WO-5225 | UT-1151 | Utilities | preventive | performance test | Check completed inside tolerance, next interval retained |
| 2023-07-04 | ME-110 | WO-5226 | P-1131 | Cooling Water | preventive | coupling alignment check | Consumable renewed, condition confirmed normal |
| 2023-07-11 | ME-111 | WO-5227 | F-1043 | Crude Distillation | preventive | refractory inspection | Consumable renewed, condition confirmed normal |
| 2023-07-18 | ME-112 | WO-5228 | P-1061 | Naphtha Hydrotreater | preventive | suction strainer cleaning | Minor wear noted, no immediate action |
| 2023-07-25 | ME-113 | WO-5229 | V-1103 | Crude Storage | preventive | seat leakage check | Consumable renewed, condition confirmed normal |
| 2023-08-01 | ME-114 | WO-5230 | ESD-1181 | Safety Systems | corrective | final element stroke test | Component replaced, post-work survey inside the normal band |
| 2023-08-08 | ME-115 | WO-5231 | F-1072 | Catalytic Reforming | preventive | burner management check | Consumable renewed, condition confirmed normal |
| 2023-08-15 | ME-116 | WO-5232 | VS-1081 | FCC | preventive | wall-thickness survey | Consumable renewed, condition confirmed normal |
| 2023-08-22 | ME-117 | WO-5233 | C-1082 | FCC | corrective | bearing temperature survey | Temporary repair applied, follow-up work order raised |
| 2023-08-29 | ME-118 | WO-5234 | E-1054 | Vacuum Distillation | preventive | delta-P trend review and cleaning assessment | Minor wear noted, no immediate action |
| 2023-09-05 | ME-119 | WO-5235 | VS-1081 | FCC | preventive | internals inspection | Check completed inside tolerance, next interval retained |
| 2023-09-12 | ME-120 | WO-5236 | E-1004 | Crude Receiving | preventive | delta-P trend review and cleaning assessment | No findings, next inspection interval retained |
| 2023-09-19 | ME-121 | WO-5237 | P-1127 | Sulfur Recovery | corrective | suction strainer cleaning | Fault corrected, equipment returned to service inside the normal band |
| 2023-09-26 | ME-122 | WO-5238 | C-1112 | Hydrogen | preventive | anti-surge valve stroke test | Consumable renewed, condition confirmed normal |
| 2023-10-03 | ME-123 | WO-5239 | V-1103 | Crude Storage | corrective | seat leakage check | Component replaced, post-work survey inside the normal band |
| 2023-10-10 | ME-124 | WO-5240 | F-1111 | Hydrogen | preventive | tube skin-temperature survey | Minor wear noted, no immediate action |
| 2023-10-17 | ME-125 | WO-5241 | COL-1052 | Vacuum Distillation | corrective | pressure envelope survey | Deviation cleared after adjustment, trend review scheduled |
| 2023-10-24 | ME-126 | WO-5242 | P-1131 | Cooling Water | corrective | impeller wear check | Temporary repair applied, follow-up work order raised |
| 2023-10-31 | ME-127 | WO-5243 | E-1093 | Diesel Hydrotreater | preventive | shell-side flow verification | Consumable renewed, condition confirmed normal |
| 2023-11-07 | ME-128 | WO-5244 | P-1001 | Crude Receiving | corrective | mechanical seal inspection | Component replaced, post-work survey inside the normal band |
| 2023-11-14 | ME-129 | WO-5245 | C-1112 | Hydrogen | preventive | surge margin check | Minor wear noted, no immediate action |
| 2023-11-21 | ME-130 | WO-5246 | E-1083 | FCC | corrective | shell-side flow verification | Fault corrected, equipment returned to service inside the normal band |
| 2023-11-28 | ME-131 | WO-5247 | VS-1073 | Catalytic Reforming | preventive | level instrument calibration | No findings, next inspection interval retained |
| 2023-12-05 | ME-132 | WO-5248 | VS-1073 | Catalytic Reforming | preventive | level instrument calibration | Minor wear noted, no immediate action |
| 2023-12-12 | ME-133 | WO-5249 | COL-1052 | Vacuum Distillation | preventive | pressure envelope survey | Check completed inside tolerance, next interval retained |
| 2023-12-19 | ME-134 | WO-5250 | ESD-1182 | Safety Systems | corrective | detector calibration | Component replaced, post-work survey inside the normal band |
| 2023-12-26 | ME-135 | WO-5251 | P-1127 | Sulfur Recovery | preventive | impeller wear check | Minor wear noted, no immediate action |
| 2024-01-02 | ME-136 | WO-5700 | UT-1151 | Utilities | preventive | performance test | Minor wear noted, no immediate action |
| 2024-01-09 | ME-137 | WO-5701 | V-1103 | Crude Storage | corrective | stroke test and position feedback calibration | Fault corrected, equipment returned to service inside the normal band |
| 2024-01-16 | ME-138 | WO-5702 | UT-1161 | Flare | preventive | performance test | No findings, next inspection interval retained |
| 2024-01-23 | ME-139 | WO-5703 | F-1111 | Hydrogen | corrective | burner management check | Temporary repair applied, follow-up work order raised |
| 2024-01-30 | ME-140 | WO-5704 | COL-1044 | Crude Distillation | corrective | pressure envelope survey | Deviation cleared after adjustment, trend review scheduled |
| 2024-02-06 | ME-141 | WO-5705 | V-1103 | Crude Storage | corrective | seat leakage check | Deviation cleared after adjustment, trend review scheduled |
| 2024-02-13 | ME-142 | WO-5706 | E-1083 | FCC | preventive | shell-side flow verification | Check completed inside tolerance, next interval retained |
| 2024-02-20 | ME-143 | WO-5707 | VS-1172 | Wastewater | corrective | level instrument calibration | Component replaced, post-work survey inside the normal band |
| 2024-02-27 | ME-144 | WO-5708 | VS-1113 | Hydrogen | preventive | relief valve recertification | Consumable renewed, condition confirmed normal |
| 2024-03-05 | ME-145 | WO-5709 | TK-1122 | Product Storage | corrective | roof seal inspection | Component replaced, post-work survey inside the normal band |
| 2024-03-12 | ME-146 | WO-5710 | C-1112 | Hydrogen | preventive | anti-surge valve stroke test | No findings, next inspection interval retained |
| 2024-03-19 | ME-147 | WO-5711 | UT-1161 | Flare | preventive | structural inspection | Minor wear noted, no immediate action |
| 2024-03-26 | ME-148 | WO-5712 | E-1063 | Naphtha Hydrotreater | preventive | tube bundle eddy-current survey | No findings, next inspection interval retained |
| 2024-04-02 | ME-149 | WO-5713 | E-1004 | Crude Receiving | preventive | gasket and flange inspection | Check completed inside tolerance, next interval retained |
| 2024-04-09 | ME-150 | WO-5714 | COL-1044 | Crude Distillation | preventive | tray efficiency assessment | Minor wear noted, no immediate action |
| 2024-04-16 | ME-151 | WO-5715 | P-1091 | Diesel Hydrotreater | preventive | bearing lubrication and vibration survey | Check completed inside tolerance, next interval retained |
| 2024-04-23 | ME-152 | WO-5716 | TK-1121 | Product Storage | preventive | external visual inspection | Consumable renewed, condition confirmed normal |
| 2024-04-30 | ME-153 | WO-5717 | P-1001 | Crude Receiving | preventive | suction strainer cleaning | No findings, next inspection interval retained |
| 2024-05-07 | ME-154 | WO-5718 | P-1061 | Naphtha Hydrotreater | corrective | impeller wear check | Deviation cleared after adjustment, trend review scheduled |
| 2024-05-14 | ME-155 | WO-5719 | TK-1101 | Crude Storage | corrective | roof seal inspection | Fault corrected, equipment returned to service inside the normal band |
| 2024-05-21 | ME-156 | WO-5720 | P-1061 | Naphtha Hydrotreater | corrective | coupling alignment check | Component replaced, post-work survey inside the normal band |
| 2024-05-28 | ME-157 | WO-5721 | P-1084 | FCC | corrective | impeller wear check | Temporary repair applied, follow-up work order raised |
| 2024-06-04 | ME-158 | WO-5722 | COL-1044 | Crude Distillation | preventive | level and temperature loop verification | No findings, next inspection interval retained |
| 2024-06-11 | ME-159 | WO-5723 | E-1054 | Vacuum Distillation | preventive | delta-P trend review and cleaning assessment | No findings, next inspection interval retained |
| 2024-06-18 | ME-160 | WO-5724 | P-1051 | Vacuum Distillation | preventive | impeller wear check | No findings, next inspection interval retained |
| 2024-06-25 | ME-161 | WO-5725 | TK-1122 | Product Storage | preventive | internal floating roof check | Consumable renewed, condition confirmed normal |
| 2024-07-02 | ME-162 | WO-5726 | E-1083 | FCC | preventive | delta-P trend review and cleaning assessment | Consumable renewed, condition confirmed normal |
| 2024-07-09 | ME-163 | WO-5727 | TK-1122 | Product Storage | preventive | roof seal inspection | No findings, next inspection interval retained |
| 2024-07-16 | ME-164 | WO-5728 | E-1045 | Crude Distillation | preventive | shell-side flow verification | Consumable renewed, condition confirmed normal |
| 2024-07-23 | ME-165 | WO-5729 | TK-1121 | Product Storage | corrective | internal floating roof check | Temporary repair applied, follow-up work order raised |
| 2024-07-30 | ME-166 | WO-5730 | UT-1161 | Flare | preventive | structural inspection | Minor wear noted, no immediate action |
| 2024-08-06 | ME-167 | WO-5731 | E-1093 | Diesel Hydrotreater | preventive | gasket and flange inspection | Minor wear noted, no immediate action |
| 2024-08-13 | ME-168 | WO-5732 | P-1061 | Naphtha Hydrotreater | corrective | bearing lubrication and vibration survey | Fault corrected, equipment returned to service inside the normal band |
| 2024-08-20 | ME-169 | WO-5733 | P-1051 | Vacuum Distillation | preventive | suction strainer cleaning | No findings, next inspection interval retained |
| 2024-08-27 | ME-170 | WO-5734 | P-1051 | Vacuum Distillation | preventive | coupling alignment check | Minor wear noted, no immediate action |
| 2024-09-03 | ME-171 | WO-5735 | V-1103 | Crude Storage | preventive | packing replacement | Check completed inside tolerance, next interval retained |
| 2024-09-10 | ME-172 | WO-5736 | E-1054 | Vacuum Distillation | preventive | shell-side flow verification | Check completed inside tolerance, next interval retained |
| 2024-09-17 | ME-173 | WO-5737 | E-1093 | Diesel Hydrotreater | preventive | shell-side flow verification | Check completed inside tolerance, next interval retained |
| 2024-09-24 | ME-174 | WO-5738 | UT-1133 | Cooling Water | preventive | structural inspection | Minor wear noted, no immediate action |
| 2024-10-01 | ME-175 | WO-5739 | ESD-1181 | Safety Systems | preventive | final element stroke test | Check completed inside tolerance, next interval retained |
| 2024-10-08 | ME-176 | WO-5740 | P-1127 | Sulfur Recovery | preventive | bearing lubrication and vibration survey | Minor wear noted, no immediate action |
| 2024-10-15 | ME-177 | WO-5741 | UT-1133 | Cooling Water | preventive | structural inspection | Minor wear noted, no immediate action |
| 2024-10-22 | ME-178 | WO-5742 | V-1103 | Crude Storage | preventive | seat leakage check | Minor wear noted, no immediate action |
| 2024-10-29 | ME-179 | WO-5743 | E-1063 | Naphtha Hydrotreater | corrective | shell-side flow verification | Deviation cleared after adjustment, trend review scheduled |
| 2024-11-05 | ME-180 | WO-5744 | UT-1133 | Cooling Water | preventive | structural inspection | Consumable renewed, condition confirmed normal |
| 2024-11-12 | ME-181 | WO-5745 | P-1061 | Naphtha Hydrotreater | preventive | suction strainer cleaning | Check completed inside tolerance, next interval retained |
| 2024-11-19 | ME-182 | WO-5746 | P-1131 | Cooling Water | preventive | suction strainer cleaning | Check completed inside tolerance, next interval retained |
| 2024-11-26 | ME-183 | WO-5747 | VS-1172 | Wastewater | preventive | relief valve recertification | Minor wear noted, no immediate action |
| 2024-12-03 | ME-184 | WO-5748 | COL-1052 | Vacuum Distillation | corrective | pressure envelope survey | Deviation cleared after adjustment, trend review scheduled |
| 2024-12-10 | ME-185 | WO-5749 | C-1125 | Sulfur Recovery | preventive | bearing temperature survey | No findings, next inspection interval retained |
| 2024-12-17 | ME-186 | WO-5750 | E-1083 | FCC | corrective | delta-P trend review and cleaning assessment | Fault corrected, equipment returned to service inside the normal band |
| 2024-12-24 | ME-187 | WO-5751 | VS-1062 | Naphtha Hydrotreater | corrective | level instrument calibration | Deviation cleared after adjustment, trend review scheduled |
| 2024-12-31 | ME-188 | WO-5752 | C-1053 | Vacuum Distillation | preventive | rotor alignment check | Minor wear noted, no immediate action |
| 2025-01-07 | ME-189 | WO-6100 | VS-1126 | Sulfur Recovery | corrective | wall-thickness survey | Fault corrected, equipment returned to service inside the normal band |
| 2025-01-14 | ME-190 | WO-6101 | V-1047 | Crude Distillation | preventive | seat leakage check | Consumable renewed, condition confirmed normal |
| 2025-01-21 | ME-191 | WO-6102 | P-1132 | Cooling Water | corrective | impeller wear check | Temporary repair applied, follow-up work order raised |
| 2025-01-28 | ME-192 | WO-6103 | P-1132 | Cooling Water | preventive | bearing lubrication and vibration survey | Minor wear noted, no immediate action |
| 2025-02-04 | ME-193 | WO-6104 | COL-1044 | Crude Distillation | preventive | level and temperature loop verification | No findings, next inspection interval retained |
| 2025-02-11 | ME-194 | WO-6105 | TK-1102 | Crude Storage | preventive | roof seal inspection | No findings, next inspection interval retained |
| 2025-02-18 | ME-195 | WO-6106 | M-1143 | Steam | corrective | bearing greasing | Temporary repair applied, follow-up work order raised |
| 2025-02-25 | ME-196 | WO-6107 | C-1152 | Utilities | corrective | bearing temperature survey | Component replaced, post-work survey inside the normal band |
| 2025-03-04 | ME-197 | WO-6108 | V-1203 | Desalter | preventive | stroke test and position feedback calibration | Check completed inside tolerance, next interval retained |
| 2025-03-16 | ME-198 | WO-6120 | C-1071 | Catalytic Reforming | corrective | drive-end bearing replacement, OEM spare fitted, post-repair hot alignment | Bearing replaced with OEM spare, alignment verified, re-baselined at 5.69 mm/s |
| 2025-03-18 | ME-199 | WO-6109 | VS-1062 | Naphtha Hydrotreater | preventive | level instrument calibration | Consumable renewed, condition confirmed normal |
| 2025-03-25 | ME-200 | WO-6110 | TK-1122 | Product Storage | corrective | external visual inspection | Fault corrected, equipment returned to service inside the normal band |
| 2025-04-01 | ME-201 | WO-6111 | V-1203 | Desalter | corrective | actuator overhaul | Fault corrected, equipment returned to service inside the normal band |
| 2025-04-08 | ME-202 | WO-6112 | F-1111 | Hydrogen | preventive | draft and excess-oxygen survey | Minor wear noted, no immediate action |
| 2025-04-15 | ME-203 | WO-6113 | P-1001 | Crude Receiving | preventive | motor current signature test | Minor wear noted, no immediate action |
| 2025-04-22 | ME-204 | WO-6114 | M-1143 | Steam | preventive | cooling air path inspection | Consumable renewed, condition confirmed normal |
| 2025-04-29 | ME-205 | WO-6115 | M-1143 | Steam | preventive | bearing greasing | Consumable renewed, condition confirmed normal |
| 2025-05-06 | ME-206 | WO-6116 | P-1131 | Cooling Water | preventive | motor current signature test | No findings, next inspection interval retained |
| 2025-05-13 | ME-207 | WO-6117 | TK-1121 | Product Storage | preventive | roof seal inspection | No findings, next inspection interval retained |
| 2025-05-20 | ME-208 | WO-6118 | VS-1046 | Crude Distillation | corrective | wall-thickness survey | Temporary repair applied, follow-up work order raised |
| 2025-05-27 | ME-209 | WO-6119 | C-1053 | Vacuum Distillation | preventive | dry gas seal inspection | Check completed inside tolerance, next interval retained |
| 2025-06-03 | ME-210 | WO-6121 | P-1084 | FCC | preventive | impeller wear check | Minor wear noted, no immediate action |
| 2025-06-10 | ME-211 | WO-6122 | VS-1073 | Catalytic Reforming | corrective | relief valve recertification | Deviation cleared after adjustment, trend review scheduled |
| 2025-06-17 | ME-212 | WO-6123 | P-1084 | FCC | corrective | impeller wear check | Component replaced, post-work survey inside the normal band |
| 2025-06-24 | ME-213 | WO-6124 | P-1202 | Desalter | corrective | coupling alignment check | Component replaced, post-work survey inside the normal band |
| 2025-07-01 | ME-214 | WO-6125 | TK-1123 | Product Storage | corrective | external visual inspection | Deviation cleared after adjustment, trend review scheduled |
| 2025-07-08 | ME-215 | WO-6126 | P-1002 | Crude Receiving | preventive | bearing lubrication and vibration survey | No findings, next inspection interval retained |
| 2025-07-15 | ME-216 | WO-6127 | E-1083 | FCC | preventive | delta-P trend review and cleaning assessment | Consumable renewed, condition confirmed normal |
| 2025-07-22 | ME-217 | WO-6128 | VS-1162 | Flare | corrective | internals inspection | Component replaced, post-work survey inside the normal band |
| 2025-07-29 | ME-218 | WO-6129 | P-1202 | Desalter | corrective | suction strainer cleaning | Deviation cleared after adjustment, trend review scheduled |
| 2025-08-05 | ME-219 | WO-6130 | E-1063 | Naphtha Hydrotreater | preventive | delta-P trend review and cleaning assessment | Consumable renewed, condition confirmed normal |
| 2025-08-12 | ME-220 | WO-6131 | P-1132 | Cooling Water | preventive | coupling alignment check | Minor wear noted, no immediate action |
| 2025-08-19 | ME-221 | WO-6132 | P-1132 | Cooling Water | preventive | bearing lubrication and vibration survey | Consumable renewed, condition confirmed normal |
| 2025-08-26 | ME-222 | WO-6133 | C-1152 | Utilities | preventive | bearing temperature survey | Check completed inside tolerance, next interval retained |
| 2025-09-02 | ME-223 | WO-6134 | P-1042 | Crude Distillation | preventive | suction strainer cleaning | No findings, next inspection interval retained |
| 2025-09-09 | ME-224 | WO-6135 | E-1083 | FCC | corrective | gasket and flange inspection | Fault corrected, equipment returned to service inside the normal band |
| 2025-09-16 | ME-225 | WO-6136 | V-1047 | Crude Distillation | preventive | seat leakage check | No findings, next inspection interval retained |
| 2025-09-23 | ME-226 | WO-6137 | P-1142 | Steam | preventive | bearing lubrication and vibration survey | Check completed inside tolerance, next interval retained |
| 2025-09-30 | ME-227 | WO-6138 | V-1003 | Crude Receiving | preventive | actuator overhaul | Consumable renewed, condition confirmed normal |
| 2025-10-07 | ME-228 | WO-6139 | UT-1151 | Utilities | preventive | structural inspection | Check completed inside tolerance, next interval retained |
| 2025-10-14 | ME-229 | WO-6140 | P-1084 | FCC | corrective | motor current signature test | Fault corrected, equipment returned to service inside the normal band |
| 2025-10-21 | ME-230 | WO-6141 | P-1001 | Crude Receiving | preventive | bearing lubrication and vibration survey | Check completed inside tolerance, next interval retained |
| 2025-10-28 | ME-231 | WO-6142 | E-1063 | Naphtha Hydrotreater | preventive | shell-side flow verification | Minor wear noted, no immediate action |
| 2025-11-02 | ME-232 | WO-2417 | C-1071 | Catalytic Reforming | preventive | hot alignment check, coupling offset 0.06 mm against 0.10 mm tolerance | Coupling offset 0.06 mm within 0.10 mm tolerance; no correction |
| 2025-11-04 | ME-233 | WO-6143 | P-1061 | Naphtha Hydrotreater | preventive | mechanical seal inspection | Minor wear noted, no immediate action |
| 2025-11-11 | ME-234 | WO-6144 | C-1082 | FCC | corrective | lube-oil sampling and analysis | Temporary repair applied, follow-up work order raised |
| 2025-11-18 | ME-235 | WO-6145 | TK-1123 | Product Storage | corrective | external visual inspection | Temporary repair applied, follow-up work order raised |
| 2025-11-25 | ME-236 | WO-6146 | TK-1102 | Crude Storage | corrective | internal floating roof check | Deviation cleared after adjustment, trend review scheduled |
| 2025-12-02 | ME-237 | WO-6147 | C-1071 | Catalytic Reforming | corrective | rotor alignment check | Deviation cleared after adjustment, trend review scheduled |
| 2025-12-09 | ME-238 | WO-6148 | P-1084 | FCC | preventive | bearing lubrication and vibration survey | No findings, next inspection interval retained |
| 2025-12-16 | ME-239 | WO-6149 | P-1061 | Naphtha Hydrotreater | corrective | motor current signature test | Fault corrected, equipment returned to service inside the normal band |
| 2025-12-23 | ME-240 | WO-6150 | P-1091 | Diesel Hydrotreater | corrective | bearing lubrication and vibration survey | Temporary repair applied, follow-up work order raised |
| 2025-12-30 | ME-241 | WO-6151 | P-1124 | Product Storage | preventive | impeller wear check | Check completed inside tolerance, next interval retained |
| 2026-01-06 | ME-242 | WO-8600 | P-1127 | Sulfur Recovery | preventive | impeller wear check | Check completed inside tolerance, next interval retained |
| 2026-01-13 | ME-243 | WO-8601 | E-1083 | FCC | preventive | shell-side flow verification | Minor wear noted, no immediate action |
| 2026-01-20 | ME-244 | WO-8602 | E-1045 | Crude Distillation | preventive | shell-side flow verification | No findings, next inspection interval retained |
| 2026-01-27 | ME-245 | WO-8603 | VS-1092 | Diesel Hydrotreater | corrective | relief valve recertification | Deviation cleared after adjustment, trend review scheduled |
| 2026-02-03 | ME-246 | WO-8604 | P-1042 | Crude Distillation | corrective | mechanical seal inspection | Component replaced, post-work survey inside the normal band |
| 2026-02-10 | ME-247 | WO-8605 | C-1071 | Catalytic Reforming | preventive | lube-oil sampling and analysis | No findings, next inspection interval retained |
| 2026-02-17 | ME-248 | WO-8606 | TK-1101 | Crude Storage | corrective | external visual inspection | Fault corrected, equipment returned to service inside the normal band |
| 2026-02-24 | ME-249 | WO-8607 | P-1202 | Desalter | corrective | bearing lubrication and vibration survey | Temporary repair applied, follow-up work order raised |
| 2026-03-03 | ME-250 | WO-8608 | UT-1133 | Cooling Water | preventive | performance test | Minor wear noted, no immediate action |
| 2026-03-10 | ME-251 | WO-8609 | UT-1133 | Cooling Water | corrective | control loop verification | Temporary repair applied, follow-up work order raised |
| 2026-03-17 | ME-252 | WO-8610 | C-1071 | Catalytic Reforming | preventive | rotor alignment check | No findings, next inspection interval retained |
| 2026-03-24 | ME-253 | WO-8611 | P-1051 | Vacuum Distillation | preventive | motor current signature test | Minor wear noted, no immediate action |
| 2026-03-31 | ME-254 | WO-8612 | V-1003 | Crude Receiving | corrective | seat leakage check | Deviation cleared after adjustment, trend review scheduled |
| 2026-04-07 | ME-255 | WO-8613 | VS-1073 | Catalytic Reforming | preventive | level instrument calibration | No findings, next inspection interval retained |
| 2026-04-14 | ME-256 | WO-8614 | UT-1151 | Utilities | preventive | structural inspection | Minor wear noted, no immediate action |
| 2026-04-21 | ME-257 | WO-8615 | P-1142 | Steam | preventive | motor current signature test | Check completed inside tolerance, next interval retained |
| 2026-04-28 | ME-258 | WO-8616 | UT-1161 | Flare | corrective | control loop verification | Temporary repair applied, follow-up work order raised |
| 2026-05-05 | ME-259 | WO-8617 | ESD-1182 | Safety Systems | corrective | detector calibration | Temporary repair applied, follow-up work order raised |
| 2026-05-12 | ME-260 | WO-8618 | P-1171 | Wastewater | preventive | mechanical seal inspection | Minor wear noted, no immediate action |
| 2026-05-19 | ME-261 | WO-8619 | P-1042 | Crude Distillation | preventive | mechanical seal inspection | Minor wear noted, no immediate action |
| 2026-05-26 | ME-262 | WO-8620 | TK-1122 | Product Storage | preventive | external visual inspection | Minor wear noted, no immediate action |
| 2026-06-02 | ME-263 | WO-8621 | C-1071 | Catalytic Reforming | preventive | surge margin check | No findings, next inspection interval retained |
| 2026-06-09 | ME-264 | WO-8622 | TK-1101 | Crude Storage | preventive | level transmitter calibration | Minor wear noted, no immediate action |
| 2026-06-16 | ME-265 | WO-8623 | F-1141 | Steam | preventive | tube skin-temperature survey | Consumable renewed, condition confirmed normal |
| 2026-06-23 | ME-266 | WO-8624 | VS-1062 | Naphtha Hydrotreater | corrective | level instrument calibration | Temporary repair applied, follow-up work order raised |
| 2026-06-30 | ME-267 | WO-8625 | P-1042 | Crude Distillation | preventive | bearing lubrication and vibration survey | No findings, next inspection interval retained |
| 2026-07-07 | ME-268 | WO-8626 | P-1001 | Crude Receiving | preventive | coupling alignment check | Consumable renewed, condition confirmed normal |
| 2026-07-14 | ME-269 | WO-8627 | P-1091 | Diesel Hydrotreater | preventive | suction strainer cleaning | No findings, next inspection interval retained |
| 2026-07-21 | ME-270 | WO-8628 | VS-1162 | Flare | preventive | level instrument calibration | No findings, next inspection interval retained |
| 2026-07-28 | ME-271 | WO-8629 | P-1091 | Diesel Hydrotreater | corrective | bearing lubrication and vibration survey | Component replaced, post-work survey inside the normal band |
| 2026-08-04 | ME-272 | WO-8630 | UT-1161 | Flare | preventive | structural inspection | Check completed inside tolerance, next interval retained |
| 2026-08-11 | ME-273 | WO-8631 | V-1047 | Crude Distillation | corrective | packing replacement | Temporary repair applied, follow-up work order raised |
| 2026-08-18 | ME-274 | WO-8802 | TK-1121 | Product Storage | preventive | six-monthly external visual inspection, no findings | No findings, next inspection interval retained |
| 2026-08-25 | ME-275 | WO-8632 | F-1111 | Hydrogen | preventive | refractory inspection | Consumable renewed, condition confirmed normal |
| 2026-08-26 | ME-276 | WO-8810 | E-1063 | Naphtha Hydrotreater | preventive | quarterly delta-P trend review, no action expected | Check completed inside tolerance, next interval retained |
| 2026-09-01 | ME-277 | WO-8633 | C-1125 | Sulfur Recovery | preventive | bearing temperature survey | Consumable renewed, condition confirmed normal |
| 2026-09-03 | ME-278 | WO-8837 | V-1047 | Crude Distillation | corrective | high level alarm response, level loop verified and drained | Temporary repair applied, follow-up work order raised |
| 2026-09-04 | ME-279 | WO-8841 | P-1042 | Crude Distillation | corrective | discharge pressure investigation, relief path and impeller check | Temporary repair applied, follow-up work order raised |
| 2026-09-07 | ME-280 | WO-8852 | C-1071 | Catalytic Reforming | corrective | drive-end bearing inspection raised from IR-204; pending approval | Open, pending approval APR-231 |
| 2026-09-08 | ME-281 | WO-8634 | P-1171 | Wastewater | preventive | impeller wear check | Check completed inside tolerance, next interval retained |
| 2026-09-15 | ME-282 | WO-8635 | C-1152 | Utilities | corrective | lube-oil sampling and analysis | Component replaced, post-work survey inside the normal band |
| 2026-09-22 | ME-283 | WO-8636 | E-1045 | Crude Distillation | corrective | tube bundle eddy-current survey | Temporary repair applied, follow-up work order raised |
| 2026-09-29 | ME-284 | WO-8637 | COL-1052 | Vacuum Distillation | preventive | level and temperature loop verification | No findings, next inspection interval retained |

### 7.7 Work-order numbering

Work order numbers are sequential within a calendar year and the series ascends across the period: 2021 uses 41xx, 2022 uses 47xx, 2023 uses 52xx, 2024 uses 57xx, 2025 uses 61xx and 2026 uses 86xx after the CMMS migration. Three numbers are fixed by the console narrative and appear out of series by design: **WO-2417** (C-3 coupling alignment, raised 2022 and re-executed 2025-11-02), **WO-6120** (C-3 drive-end bearing replacement, 2025-03-16) and the 2026 series **WO-8802**, **WO-8810**, **WO-8837**, **WO-8841** and **WO-8852**.

### 7.8 Maintenance by area

| Area | Events | Preventive | Corrective | Last event |
|---|---|---|---|---|
| Crude Receiving | 15 | 11 | 4 | 2026-07-07 |
| Crude Storage | 18 | 8 | 10 | 2026-06-09 |
| Desalter | 12 | 5 | 7 | 2026-02-24 |
| Crude Distillation | 29 | 18 | 11 | 2026-09-22 |
| Vacuum Distillation | 21 | 14 | 7 | 2026-09-29 |
| Naphtha Hydrotreater | 20 | 13 | 7 | 2026-08-26 |
| Catalytic Reforming | 15 | 9 | 6 | 2026-09-07 |
| FCC | 23 | 10 | 13 | 2026-01-13 |
| Diesel Hydrotreater | 14 | 8 | 6 | 2026-07-28 |
| Sulfur Recovery | 18 | 10 | 8 | 2026-09-01 |
| Hydrogen | 14 | 9 | 5 | 2026-08-25 |
| Product Storage | 20 | 11 | 9 | 2026-08-18 |
| Utilities | 11 | 8 | 3 | 2026-09-15 |
| Steam | 10 | 9 | 1 | 2026-06-16 |
| Cooling Water | 18 | 13 | 5 | 2026-03-10 |
| Flare | 13 | 8 | 5 | 2026-08-04 |
| Wastewater | 7 | 6 | 1 | 2026-09-08 |
| Safety Systems | 6 | 3 | 3 | 2026-05-05 |

Corrective share is the useful column: areas whose corrective share exceeds half are running reactively, and areas below a third are running on their preventive plan. The rotating-equipment areas sit at the top of the corrective share, which is consistent with the failure-mode frequency table in Section 13.4.

### 7.8.1 Crude Receiving

**Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

### 7.8.2 Crude Storage

**Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

### 7.8.3 Desalter

**Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

### 7.8.4 Crude Distillation

**Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

### 7.8.5 Vacuum Distillation

**Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

### 7.8.6 Naphtha Hydrotreater

**Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

### 7.8.7 Catalytic Reforming

**Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

### 7.8.8 FCC

**FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

### 7.8.9 Diesel Hydrotreater

**Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

### 7.8.10 Sulfur Recovery

**Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

### 7.8.11 Hydrogen

**Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

### 7.8.12 Product Storage

**Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

### 7.8.13 Utilities

**Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

### 7.8.14 Steam

**Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

### 7.8.15 Cooling Water

**Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

### 7.8.16 Flare

**Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

### 7.8.17 Wastewater

**Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

### 7.8.18 Safety Systems

**Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

## 8. Inspection Records

This section carries the 28 formal inspection records raised in the period, `IR-177` through `IR-204`, in date order. Each record states the equipment, the finding and the disposition. **IR-198** is the drive-end bearing replacement and **IR-204** is the 2026 C-3 vibration survey; both are anchor documents for the C-3 history in Section 14.

| Inspection | Date | Equipment | Area | Inspector | Disposition |
|---|---|---|---|---|---|
| IR-177 | 2021-08-10 | C-1125 | Sulfur Recovery | Maintenance Execution | Oil charge replaced, no mechanical action. |
| IR-178 | 2021-10-14 | P-1124 | Product Storage | Reliability Engineering | Lubrication corrected, re-survey scheduled. |
| IR-179 | 2021-12-19 | VS-1172 | Wastewater | Third-party NDT (vendor) | Fitness-for-service interval retained. |
| IR-180 | 2022-02-22 | VS-1046 | Crude Distillation | Reliability Engineering | Fitness-for-service interval retained. |
| IR-181 | 2022-04-29 | F-1141 | Steam | Third-party NDT (vendor) | No action. |
| IR-182 | 2022-07-04 | P-1084 | FCC | Reliability Engineering | Insert replaced, soft-foot shimmed, alignment verified. |
| IR-183 | 2022-09-07 | E-1054 | Vacuum Distillation | Operations Shift | Bundle returned to service, next survey at 48 months. |
| IR-184 | 2022-11-12 | TK-1123 | Product Storage | Operations Shift | Seal section scheduled for replacement. |
| IR-185 | 2023-01-17 | COL-1052 | Vacuum Distillation | Maintenance Execution | No action, next internal survey in 24 months. |
| IR-186 | 2023-03-23 | E-1004 | Crude Receiving | Inspection Services | Cleaning deferred to the next window; trend review quarterly. |
| IR-187 | 2023-05-28 | C-1071 | Catalytic Reforming | Maintenance Execution | Actuator overhauled, stroke re-profiled. |
| IR-188 | 2023-08-02 | V-1103 | Crude Storage | Third-party NDT (vendor) | Packing re-torqued, feedback re-zeroed. |
| IR-189 | 2023-10-06 | C-1053 | Vacuum Distillation | Third-party NDT (vendor) | Oil charge replaced, no mechanical action. |
| IR-190 | 2023-12-11 | P-1091 | Diesel Hydrotreater | Maintenance Execution | Insert replaced, soft-foot shimmed, alignment verified. |
| IR-191 | 2024-02-15 | M-1143 | Steam | Inspection Services | No action. |
| IR-192 | 2024-04-20 | E-1054 | Vacuum Distillation | Maintenance Execution | Cleaning deferred to the next window; trend review quarterly. |
| IR-193 | 2024-06-25 | VS-1201 | Desalter | Maintenance Execution | Fitness-for-service interval retained. |
| IR-194 | 2024-08-30 | P-1124 | Product Storage | Maintenance Execution | Lubrication corrected, re-survey scheduled. |
| IR-195 | 2024-11-03 | P-1061 | Naphtha Hydrotreater | Reliability Engineering | Lubrication corrected, re-survey scheduled. |
| IR-196 | 2025-01-08 | C-1125 | Sulfur Recovery | Third-party NDT (vendor) | Actuator overhauled, stroke re-profiled. |
| IR-197 | 2025-03-15 | UT-1151 | Utilities | Reliability Engineering | No action. |
| IR-198 | 2025-03-16 | C-1071 | Catalytic Reforming | Third-party NDT (vendor) | Bearing replaced, alignment re-checked and accepted; returned to service. |
| IR-199 | 2025-05-20 | E-1063 | Naphtha Hydrotreater | Third-party NDT (vendor) | Cleaning deferred to the next window; trend review quarterly. |
| IR-200 | 2025-09-15 | E-1083 | FCC | Operations Shift | Bundle returned to service, next survey at 48 months. |
| IR-201 | 2026-01-11 | TK-1102 | Crude Storage | Maintenance Execution | Seal section scheduled for replacement. |
| IR-202 | 2026-05-09 | P-1124 | Product Storage | Reliability Engineering | Lubrication corrected, re-survey scheduled. |
| IR-203 | 2026-09-05 | V-1064 | Naphtha Hydrotreater | Inspection Services | Diaphragm replaced. |
| IR-204 | 2026-09-06 | C-1071 | Catalytic Reforming | Third-party NDT (vendor) | Daily monitoring imposed, corrective work order WO-8852 raised, hot alignment check required before re-baselining. |

### 8.1 IR-177 - C-1125

**Date:** 2021-08-10. **Equipment:** C-1125 (compressor), area Sulfur Recovery. **Inspector:** Maintenance Execution.

**Findings.** Rotor alignment within tolerance; lube-oil particle count ISO 18/16/13.

**Disposition.** Oil charge replaced, no mechanical action.

### 8.2 IR-178 - P-1124

**Date:** 2021-10-14. **Equipment:** P-1124 (pump), area Product Storage. **Inspector:** Reliability Engineering.

**Findings.** Bearing housing vibration 0.4 mm/s above the rolling baseline with stable temperature.

**Disposition.** Lubrication corrected, re-survey scheduled.

### 8.3 IR-179 - VS-1172

**Date:** 2021-12-19. **Equipment:** VS-1172 (vessel), area Wastewater. **Inspector:** Third-party NDT (vendor).

**Findings.** Wall thickness at the design minimum plus 1.4 mm; no blistering or cracking.

**Disposition.** Fitness-for-service interval retained.

### 8.4 IR-180 - VS-1046

**Date:** 2022-02-22. **Equipment:** VS-1046 (vessel), area Crude Distillation. **Inspector:** Reliability Engineering.

**Findings.** Wall thickness at the design minimum plus 1.4 mm; no blistering or cracking.

**Disposition.** Fitness-for-service interval retained.

### 8.5 IR-181 - F-1141

**Date:** 2022-04-29. **Equipment:** F-1141 (furnace), area Steam. **Inspector:** Third-party NDT (vendor).

**Findings.** Tube skin temperature 38 degC below the design limit; burner flame pattern even.

**Disposition.** No action.

### 8.6 IR-182 - P-1084

**Date:** 2022-07-04. **Equipment:** P-1084 (pump), area FCC. **Inspector:** Reliability Engineering.

**Findings.** Coupling insert degradation and 0.03 mm soft-foot on the drive-end foot.

**Disposition.** Insert replaced, soft-foot shimmed, alignment verified.

### 8.7 IR-183 - E-1054

**Date:** 2022-09-07. **Equipment:** E-1054 (exchanger), area Vacuum Distillation. **Inspector:** Operations Shift.

**Findings.** No tube-wall loss on the eddy-current sample; two baffle-tip clearances slightly enlarged.

**Disposition.** Bundle returned to service, next survey at 48 months.

### 8.8 IR-184 - TK-1123

**Date:** 2022-11-12. **Equipment:** TK-1123 (tank), area Product Storage. **Inspector:** Operations Shift.

**Findings.** Roof seal abrasion over a 2 m run; no product wetted surface exposed.

**Disposition.** Seal section scheduled for replacement.

### 8.9 IR-185 - COL-1052

**Date:** 2023-01-17. **Equipment:** COL-1052 (column), area Vacuum Distillation. **Inspector:** Maintenance Execution.

**Findings.** Tray pressure drop within design; two valve trays show slight weep.

**Disposition.** No action, next internal survey in 24 months.

### 8.10 IR-186 - E-1004

**Date:** 2023-03-23. **Equipment:** E-1004 (exchanger), area Crude Receiving. **Inspector:** Inspection Services.

**Findings.** Shell-side delta-P 0.42 bar against a clean 0.28 bar reference; fouling factor estimated at 0.00021 m2K/W.

**Disposition.** Cleaning deferred to the next window; trend review quarterly.

### 8.11 IR-187 - C-1071

**Date:** 2023-05-28. **Equipment:** C-1071 (compressor), area Catalytic Reforming. **Inspector:** Maintenance Execution.

**Findings.** Anti-surge valve stroke 4% slow at the closed end.

**Disposition.** Actuator overhauled, stroke re-profiled.

### 8.12 IR-188 - V-1103

**Date:** 2023-08-02. **Equipment:** V-1103 (valve), area Crude Storage. **Inspector:** Third-party NDT (vendor).

**Findings.** Position feedback tracking commanded position within 1.1%; packing weep recorded on two studs.

**Disposition.** Packing re-torqued, feedback re-zeroed.

### 8.13 IR-189 - C-1053

**Date:** 2023-10-06. **Equipment:** C-1053 (compressor), area Vacuum Distillation. **Inspector:** Third-party NDT (vendor).

**Findings.** Rotor alignment within tolerance; lube-oil particle count ISO 18/16/13.

**Disposition.** Oil charge replaced, no mechanical action.

### 8.14 IR-190 - P-1091

**Date:** 2023-12-11. **Equipment:** P-1091 (pump), area Diesel Hydrotreater. **Inspector:** Maintenance Execution.

**Findings.** Coupling insert degradation and 0.03 mm soft-foot on the drive-end foot.

**Disposition.** Insert replaced, soft-foot shimmed, alignment verified.

### 8.15 IR-191 - M-1143

**Date:** 2024-02-15. **Equipment:** M-1143 (motor), area Steam. **Inspector:** Inspection Services.

**Findings.** Insulation resistance 480 MOhm; winding thermography even.

**Disposition.** No action.

### 8.16 IR-192 - E-1054

**Date:** 2024-04-20. **Equipment:** E-1054 (exchanger), area Vacuum Distillation. **Inspector:** Maintenance Execution.

**Findings.** Shell-side delta-P 0.42 bar against a clean 0.28 bar reference; fouling factor estimated at 0.00021 m2K/W.

**Disposition.** Cleaning deferred to the next window; trend review quarterly.

### 8.17 IR-193 - VS-1201

**Date:** 2024-06-25. **Equipment:** VS-1201 (vessel), area Desalter. **Inspector:** Maintenance Execution.

**Findings.** Wall thickness at the design minimum plus 1.4 mm; no blistering or cracking.

**Disposition.** Fitness-for-service interval retained.

### 8.18 IR-194 - P-1124

**Date:** 2024-08-30. **Equipment:** P-1124 (pump), area Product Storage. **Inspector:** Maintenance Execution.

**Findings.** Bearing housing vibration 0.4 mm/s above the rolling baseline with stable temperature.

**Disposition.** Lubrication corrected, re-survey scheduled.

### 8.19 IR-195 - P-1061

**Date:** 2024-11-03. **Equipment:** P-1061 (pump), area Naphtha Hydrotreater. **Inspector:** Reliability Engineering.

**Findings.** Bearing housing vibration 0.4 mm/s above the rolling baseline with stable temperature.

**Disposition.** Lubrication corrected, re-survey scheduled.

### 8.20 IR-196 - C-1125

**Date:** 2025-01-08. **Equipment:** C-1125 (compressor), area Sulfur Recovery. **Inspector:** Third-party NDT (vendor).

**Findings.** Anti-surge valve stroke 4% slow at the closed end.

**Disposition.** Actuator overhauled, stroke re-profiled.

### 8.21 IR-197 - UT-1151

**Date:** 2025-03-15. **Equipment:** UT-1151 (utility), area Utilities. **Inspector:** Reliability Engineering.

**Findings.** Performance within 3% of the commissioned curve.

**Disposition.** No action.

### 8.22 IR-198 - C-1071

**Date:** 2025-03-16. **Equipment:** C-1071 (compressor), area Catalytic Reforming. **Inspector:** Third-party NDT (vendor).

**Findings.** Drive-end bearing removed and replaced with OEM spare following rising 1x vibration and bearing-housing temperature. Bearing outer-race spalling on two rolling elements; lube-oil varnish present on the cage. Post-repair overall vibration 5.4 mm/s against a 5.7 mm/s baseline; machine re-baselined at 5.69 mm/s.

**Disposition.** Bearing replaced, alignment re-checked and accepted; returned to service.

### 8.23 IR-199 - E-1063

**Date:** 2025-05-20. **Equipment:** E-1063 (exchanger), area Naphtha Hydrotreater. **Inspector:** Third-party NDT (vendor).

**Findings.** Shell-side delta-P 0.42 bar against a clean 0.28 bar reference; fouling factor estimated at 0.00021 m2K/W.

**Disposition.** Cleaning deferred to the next window; trend review quarterly.

### 8.24 IR-200 - E-1083

**Date:** 2025-09-15. **Equipment:** E-1083 (exchanger), area FCC. **Inspector:** Operations Shift.

**Findings.** No tube-wall loss on the eddy-current sample; two baffle-tip clearances slightly enlarged.

**Disposition.** Bundle returned to service, next survey at 48 months.

### 8.25 IR-201 - TK-1102

**Date:** 2026-01-11. **Equipment:** TK-1102 (tank), area Crude Storage. **Inspector:** Maintenance Execution.

**Findings.** Roof seal abrasion over a 2 m run; no product wetted surface exposed.

**Disposition.** Seal section scheduled for replacement.

### 8.26 IR-202 - P-1124

**Date:** 2026-05-09. **Equipment:** P-1124 (pump), area Product Storage. **Inspector:** Reliability Engineering.

**Findings.** Bearing housing vibration 0.4 mm/s above the rolling baseline with stable temperature.

**Disposition.** Lubrication corrected, re-survey scheduled.

### 8.27 IR-203 - V-1064

**Date:** 2026-09-05. **Equipment:** V-1064 (valve), area Naphtha Hydrotreater. **Inspector:** Inspection Services.

**Findings.** Actuator diaphragm perished at the stem guide.

**Disposition.** Diaphragm replaced.

### 8.28 IR-204 - C-1071

**Date:** 2026-09-06. **Equipment:** C-1071 (compressor), area Catalytic Reforming. **Inspector:** Third-party NDT (vendor).

**Findings.** Overall vibration on the drive-end bearing housing 6.8 mm/s RMS against a 90-day rolling baseline of 5.8 mm/s (an increase of 18%). Energy concentrated at 1x running speed (4.9 mm/s) with a stable 2x component and a slightly elevated bearing defect band. DE bearing-housing temperature 79 degC against a 68 degC baseline. Pattern consistent with progressive bearing wear or a developing alignment shift.

**Disposition.** Daily monitoring imposed, corrective work order WO-8852 raised, hot alignment check required before re-baselining.

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

## 10. Safety Procedures

### 10.1 Safety basis

The plant's protective layer has three tiers: process control and operator response, alarm and operator action at the warning band, and the safety instrumented system at the critical band. This section states the standing rules; the procedures themselves are registered in Section 11.

### 10.2 Lockout / tagout

SOP-11.2 rev2 governs isolation of rotating equipment: obtain a work permit referencing the work order number, isolate the electrical supply at the designated disconnect and apply a personal lock, isolate process suction and discharge and bleed to atmospheric pressure, verify zero energy state, attach tags recording permit number, time and responsible person, and remove locks only by the person who applied them or under a documented two-signature supervisor override.

### 10.3 Gas and leak detection

The register carries 8 latched detector channels. A detector reads zero when healthy and latches at full scale on a trip. A trip is treated as a real release until proven otherwise: the detector is never silenced or bypassed, the exclusion zone is set for the reported area, the release is isolated, and the detector is reset only after the release is confirmed cleared and it reads and holds zero. An incident may not be closed while any detector in the affected area remains latched (SOP-41.2 rev8).

| Detector tag | Equipment | Area | Measurement | Unit |
|---|---|---|---|---|
| GD-1043 | F-1043 | Crude Distillation | gas | ppm |
| GD-1072 | F-1072 | Catalytic Reforming | gas | ppm |
| GD-1111 | F-1111 | Hydrogen | gas | ppm |
| GD-1141 | F-1141 | Steam | gas | ppm |
| GD-1181 | ESD-1181 | Safety Systems | gas | ppm |
| LK-1181 | ESD-1181 | Safety Systems | leak | 0/1 |
| GD-1182 | ESD-1182 | Safety Systems | gas | ppm |
| LK-1182 | ESD-1182 | Safety Systems | leak | 0/1 |

### 10.4 Emergency shutdown

The safety area holds ESD-1181 (Fire & Gas Panel), ESD-1182 (Emergency Shutdown Valve). ESD-1181 is the fire and gas panel; ESD-1182 is the emergency shutdown valve. Scenario `sc-esd` exercises a controlled area shutdown initiated from ESD-1182. The shutdown philosophy is to isolate and depressurise to the flare rather than to hold inventory in a potentially leaking section, and the flare block (UT-1161 flare stack, VS-1162 flare knock-out drum) is the designated relief destination.

### 10.5 Process safety rules that recur in the record

* Never isolate a relief device to stop a surge, and never raise an alarm limit to silence an alarm (SOP-27.9 rev3).
* Crude and vacuum distillation may not run unattended with a lost column temperature or level measurement (OPS-03.2 rev4).
* A unit may continue to run with a failed instrument only when a validated alternate covers the same control objective, the operator is notified, and the condition is reviewed at the next shift handover.
* Escalate to a controlled rate reduction when two or more measurements on the same service are unavailable, when a detector is latched in the affected area, or when a downstream unit loses its only flow path.
* A second trip on the same fault damages the winding; a tripped drive is not reset until the cause is established (SOP-18.3 rev4).

### 10.6 Permit-to-work matrix

The permit type is set by the work, not by the work order priority. A high-priority work order on a non-hydrocarbon utility still takes the lighter permit; a routine work order on a hydrocarbon line still takes the full isolation permit.

| Permit type | Applies to | Isolation required | Gas test | Fire watch | Authority |
|---|---|---|---|---|---|
| Cold work | Utilities, cooling water, instrument air, non-hydrocarbon externals | None or local isolation | Not required | No | Shift supervisor |
| Hot work | Any work introducing an ignition source in a process area | Full process isolation | Required before and during | Yes | Shift supervisor plus safety |
| Confined space | Tanks, vessels, columns, knock-out drums | Full isolation and purge | Required, continuous | Standby man required | Safety officer |
| Electrical isolation | Motors, drives, panels, instrument loops | Electrical lockout at the disconnect | Not required | No | Authorised electrical person |
| Line break | Hydrocarbon, acid gas, amine, steam lines | Full isolation, drain and purge | Required at the break point | Yes | Shift supervisor |
| Rotating equipment | Pumps, compressors, motors, fans | Electrical plus process isolation (SOP-11.2) | Required for hydrocarbon service | As area dictates | Shift supervisor |
| Tank entry | TK-1101, TK-1102, TK-1121, TK-1122, TK-1123 | Full isolation, drain, purge and inert where required | Required, continuous | Yes | Safety officer |
| Excavation | Underground services and drainage | Service drawings checked and services isolated | As required | No | Shift supervisor |
| Working at height | Columns, stacks, flare, tanks | Not applicable | Not required | No | Shift supervisor |
| Radiography | Weld and wall-thickness surveys | Area barricaded | Not required | No | Safety officer |

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

## 12. Incident History

This section is the incident and event register for the review period: 36 dated rows, `INC-401` through `INC-430` and `EV-101` through `EV-106`. Severity is classified Low (no process impact, corrected at next opportunity), Medium (localised deviation, unit stayed on line), High (rate reduction or partial unit outage) or Critical (safety-relevant deviation, escalated).

| Id | Date | Equipment | Area | Measurement | Event | Severity | Cause class | Outcome |
|---|---|---|---|---|---|---|---|---|
| INC-401 | 2021-07-20 | P-1131 | Cooling Water | pressure | relief path demand during upset | Medium | process | relief path verified, no release |
| INC-402 | 2021-09-11 | P-1127 | Sulfur Recovery | vibration | overall vibration alarm above alert threshold | Medium | mechanical | daily monitoring, work order raised |
| INC-403 | 2021-11-06 | P-1084 | FCC | position | control valve stuck mid-travel | Critical | mechanical | valve isolated and stroked |
| INC-404 | 2021-12-29 | F-1043 | Crude Distillation | vibration | overall vibration alarm above alert threshold | Low | mechanical | daily monitoring, work order raised |
| INC-405 | 2022-02-20 | VS-1073 | Catalytic Reforming | flow | charge flow sag below normal band | Critical | process | upstream valve stroked, flow restored |
| INC-406 | 2022-04-15 | VS-1113 | Hydrogen | current | current draw above rated envelope | High | electrical | load rebalanced |
| INC-407 | 2022-06-08 | VS-1201 | Desalter | level | low level trip on storage tank | Medium | process | transfer rate reduced, alarm cleared |
| INC-408 | 2022-07-30 | VS-1092 | Diesel Hydrotreater | current | motor overload trip | Low | electrical | drive inspected before restart |
| INC-409 | 2022-09-23 | VS-1162 | Flare | level | low level trip on storage tank | High | process | transfer rate reduced, alarm cleared |
| INC-410 | 2022-11-16 | VS-1073 | Catalytic Reforming | level | high level alarm in separator | Low | process | level loop moved to manual and drained |
| INC-411 | 2023-01-09 | P-1042 | Crude Distillation | temperature | furnace pass temperature excursion | Low | process | firing rate reduced |
| INC-412 | 2023-03-02 | VS-1073 | Catalytic Reforming | position | valve position feedback mismatch | Medium | instrument | loop moved to manual, actuator overhauled |
| INC-413 | 2023-04-24 | V-1003 | Crude Receiving | current | current draw above rated envelope | High | electrical | load rebalanced |
| INC-414 | 2023-06-17 | COL-1052 | Vacuum Distillation | temperature | bearing temperature alarm | Medium | mechanical | load reduced, bearing inspected |
| INC-415 | 2023-08-09 | E-1083 | FCC | flow | flow restriction across blocked path | Medium | mechanical | strainer cleaned |
| INC-416 | 2023-10-02 | TK-1123 | Product Storage | temperature | outlet temperature drift | Medium | instrument | calibration work order raised |
| INC-417 | 2023-11-26 | F-1141 | Steam | temperature | outlet temperature drift | Medium | instrument | calibration work order raised |
| INC-418 | 2024-01-18 | P-1084 | FCC | position | valve position feedback mismatch | Medium | instrument | loop moved to manual, actuator overhauled |
| INC-419 | 2024-03-12 | TK-1123 | Product Storage | flow | charge flow sag below normal band | Critical | process | upstream valve stroked, flow restored |
| INC-420 | 2024-05-05 | VS-1081 | FCC | flow | charge flow sag below normal band | High | process | upstream valve stroked, flow restored |
| INC-421 | 2024-06-27 | P-1131 | Cooling Water | vibration | overall vibration alarm above alert threshold | Low | mechanical | daily monitoring, work order raised |
| INC-422 | 2024-08-20 | VS-1073 | Catalytic Reforming | level | low level trip on storage tank | Low | process | transfer rate reduced, alarm cleared |
| INC-423 | 2024-10-11 | V-1047 | Crude Distillation | current | current draw above rated envelope | High | electrical | load rebalanced |
| INC-424 | 2024-12-04 | V-1064 | Naphtha Hydrotreater | flow | flow restriction across blocked path | Medium | mechanical | strainer cleaned |
| INC-425 | 2025-01-27 | VS-1113 | Hydrogen | vibration | vibration step change on bearing housing | Medium | mechanical | machine stopped on controlled ramp |
| INC-426 | 2025-03-23 | COL-1052 | Vacuum Distillation | pressure | pressure excursion above operating limit | High | process | controlled rate reduction |
| INC-427 | 2025-05-16 | ESD-1181 | Safety Systems | position | control valve stuck mid-travel | Low | mechanical | valve isolated and stroked |
| INC-428 | 2025-07-08 | F-1111 | Hydrogen | vibration | vibration step change on bearing housing | Medium | mechanical | machine stopped on controlled ramp |
| INC-429 | 2025-08-30 | UT-1161 | Flare | vibration | overall vibration alarm above alert threshold | Critical | mechanical | daily monitoring, work order raised |
| INC-430 | 2025-10-22 | VS-1046 | Crude Distillation | vibration | overall vibration alarm above alert threshold | Low | mechanical | daily monitoring, work order raised |
| EV-101 | 2025-12-15 | COL-1044 | Crude Distillation | temperature | bearing temperature alarm | Medium | mechanical | load reduced, bearing inspected |
| EV-102 | 2026-02-06 | P-1131 | Cooling Water | flow | flow restriction across blocked path | Critical | mechanical | strainer cleaned |
| EV-103 | 2026-04-01 | C-1112 | Hydrogen | flow | flow restriction across blocked path | Low | mechanical | strainer cleaned |
| EV-104 | 2026-05-25 | P-1127 | Sulfur Recovery | level | low level trip on storage tank | Low | process | transfer rate reduced, alarm cleared |
| EV-105 | 2026-07-17 | E-1093 | Diesel Hydrotreater | flow | charge flow sag below normal band | Critical | process | upstream valve stroked, flow restored |
| EV-106 | 2026-09-03 | V-1047 | Crude Distillation | level | high level alarm 87% against an 80% setpoint | Critical | process | level loop drained and verified; WO-8837 raised; APR-218 approved priority escalation |

### 12.1 Severity distribution

| Severity | Events |
|---|---|
| Medium | 13 |
| Low | 10 |
| Critical | 7 |
| High | 6 |

### 12.2 Selected event narratives

### 12.2.1 INC-401 - P-1131 (2021-07-20)

Relief path demand during upset on P-1131 in area Cooling Water. Detector or transmitter was cross-checked against a correlated measurement. Relief path verified, no release.

### 12.2.2 INC-402 - P-1127 (2021-09-11)

Overall vibration alarm above alert threshold on P-1127 in area Sulfur Recovery. Alarm annunciated at the console and was acknowledged within the shift. Daily monitoring, work order raised.

### 12.2.3 INC-403 - P-1084 (2021-11-06)

Control valve stuck mid-travel on P-1084 in area FCC. Alarm annunciated at the console and was acknowledged within the shift. Valve isolated and stroked.

### 12.2.4 INC-404 - F-1043 (2021-12-29)

Overall vibration alarm above alert threshold on F-1043 in area Crude Distillation. Detector or transmitter was cross-checked against a correlated measurement. Daily monitoring, work order raised.

### 12.2.5 INC-405 - VS-1073 (2022-02-20)

Charge flow sag below normal band on VS-1073 in area Catalytic Reforming. Operator confirmed the reading against a redundant transmitter before acting. Upstream valve stroked, flow restored.

### 12.2.6 INC-407 - VS-1201 (2022-06-08)

Low level trip on storage tank on VS-1201 in area Desalter. Unit remained on line; the deviation was contained locally. Transfer rate reduced, alarm cleared.

### 12.2.7 INC-411 - P-1042 (2023-01-09)

Furnace pass temperature excursion on P-1042 in area Crude Distillation. Operator confirmed the reading against a redundant transmitter before acting. Firing rate reduced.

### 12.2.8 INC-415 - E-1083 (2023-08-09)

Flow restriction across blocked path on E-1083 in area FCC. Detector or transmitter was cross-checked against a correlated measurement. Strainer cleaned.

### 12.2.9 INC-419 - TK-1123 (2024-03-12)

Charge flow sag below normal band on TK-1123 in area Product Storage. Unit remained on line; the deviation was contained locally. Upstream valve stroked, flow restored.

### 12.2.10 INC-423 - V-1047 (2024-10-11)

Current draw above rated envelope on V-1047 in area Crude Distillation. Unit remained on line; the deviation was contained locally. Load rebalanced.

### 12.2.11 INC-427 - ESD-1181 (2025-05-16)

Control valve stuck mid-travel on ESD-1181 in area Safety Systems. Operator confirmed the reading against a redundant transmitter before acting. Valve isolated and stroked.

### 12.2.12 EV-101 - COL-1044 (2025-12-15)

Bearing temperature alarm on COL-1044 in area Crude Distillation. Alarm annunciated at the console and was acknowledged within the shift. Load reduced, bearing inspected.

### 12.2.13 EV-105 - E-1093 (2026-07-17)

Charge flow sag below normal band on E-1093 in area Diesel Hydrotreater. Alarm annunciated at the console and was acknowledged within the shift. Upstream valve stroked, flow restored.

### 12.2.14 EV-106 - V-1047 (2026-09-03)

High level alarm 87% against an 80% setpoint on V-1047 in area Crude Distillation. Operator confirmed the reading against a redundant transmitter before acting. Level loop drained and verified; wo-8837 raised; apr-218 approved priority escalation.

### 12.3 Cause classes

Events split across mechanical degradation (bearing, valve, impeller), process deviation (level, pressure, flow), instrument fault (transmitter failure and drift), electrical (overload and trip) and leak (seal failure and detector trip). Instrument-caused events are the most common single class, which is why SOP-14.2 and SOP-14.7 are the two most used procedures in the corpus and why every seven-instrument pump block carries a redundant pressure pair.

## 13. Reliability Analysis

Reliability is computed over the review window 2021-06-01 to 2026-09-30. Operating hours are counted from the later of the unit's commissioned date and the window start, at 24 hours per day. Failure counts are the seeded corrective event counts for each unit; MTBF is operating hours divided by failures, MTTR is the mean corrective duration in hours, and availability is `MTBF / (MTBF + MTTR)`.

### 13.1 Method and caveats

These are model-derived figures, not meter readings. They are internally consistent with the maintenance register and are reproducible from the fixed seed. The absolute values matter less than the ordering: rotating equipment dominates unplanned work, and the two assets under open corrective work (C-1071 and P-1042) sit at the bottom of the availability table, which is why they are the subjects of Sections 14 and 15.

### 13.2 Availability by unit

| Tag | Name | Area | Failures | MTBF (h) | MTTR (h) | Availability % | Last failure |
|---|---|---|---|---|---|---|---|
| P-1001 | Offloading Pump A | Crude Receiving | 1 | 46728 | 10.2 | 99.978 | 2023-11-07 |
| P-1002 | Offloading Pump B | Crude Receiving | 3 | 15336 | 18.5 | 99.880 | 2023-05-09 |
| V-1003 | Receiving Header Valve | Crude Receiving | 1 | 45288 | 20.6 | 99.955 | 2026-03-31 |
| E-1004 | Crude Preheater | Crude Receiving | 2 | 22284 | 19.8 | 99.911 | - |
| TK-1101 | Crude Tank 1 | Crude Storage | 2 | 23364 | 9.5 | 99.959 | 2026-02-17 |
| TK-1102 | Crude Tank 2 | Crude Storage | 3 | 15256 | 10.9 | 99.929 | 2025-11-25 |
| V-1103 | Tank Outlet Valve | Crude Storage | 6 | 7468 | 5.3 | 99.929 | 2024-02-06 |
| VS-1201 | Desalter Vessel | Desalter | 6 | 7788 | 6.1 | 99.922 | - |
| P-1202 | Desalter Water Pump | Desalter | 2 | 22884 | 10.5 | 99.954 | 2026-02-24 |
| V-1203 | Brine Outlet Valve | Desalter | 4 | 11202 | 9.5 | 99.915 | 2025-04-01 |
| P-1042 | Crude Charge Pump | Crude Distillation | 5 | 9202 | 19.9 | 99.784 | 2026-09-04 |
| F-1043 | Crude Charge Heater | Crude Distillation | 4 | 11292 | 4.7 | 99.958 | - |
| COL-1044 | Atmospheric Column | Crude Distillation | 1 | 44304 | 11.5 | 99.974 | 2024-01-30 |
| E-1045 | Overhead Condenser | Crude Distillation | 4 | 10860 | 5.1 | 99.953 | 2026-09-22 |
| VS-1046 | Reflux Drum | Crude Distillation | 1 | 42600 | 15.5 | 99.964 | 2025-05-20 |
| V-1047 | Column Feed Valve | Crude Distillation | 6 | 6956 | 14.1 | 99.798 | 2026-09-03 |
| P-1051 | VDU Feed Pump | Vacuum Distillation | 3 | 15336 | 19.6 | 99.872 | 2022-12-13 |
| COL-1052 | Vacuum Column | Vacuum Distillation | 4 | 11184 | 7.3 | 99.935 | 2024-12-03 |
| C-1053 | Vacuum Ejector Compressor | Vacuum Distillation | 2 | 21720 | 21.9 | 99.899 | 2023-06-06 |
| E-1054 | Vacuum Resid Cooler | Vacuum Distillation | 1 | 42168 | 22.3 | 99.947 | - |
| P-1061 | NHT Feed Pump | Naphtha Hydrotreater | 2 | 23004 | 12.5 | 99.946 | 2025-12-16 |
| VS-1062 | NHT Reactor | Naphtha Hydrotreater | 5 | 8947 | 12.7 | 99.858 | 2026-06-23 |
| E-1063 | NHT Effluent Cooler | Naphtha Hydrotreater | 2 | 21720 | 15.8 | 99.927 | 2024-10-29 |
| V-1064 | Stripper Level Valve | Naphtha Hydrotreater | 5 | 8434 | 21.9 | 99.741 | - |
| C-1071 | Reformer Recycle Compressor | Catalytic Reforming | 2 | 23208 | 23.9 | 99.897 | 2026-09-07 |
| F-1072 | Reformer Charge Heater | Catalytic Reforming | 3 | 14768 | 4.1 | 99.972 | 2021-07-27 |
| VS-1073 | Reformer Separator | Catalytic Reforming | 4 | 10650 | 9.9 | 99.907 | 2025-06-10 |
| VS-1081 | FCC Reactor | FCC | 3 | 14352 | 14.2 | 99.901 | - |
| C-1082 | Main Air Blower | FCC | 5 | 8362 | 17.4 | 99.792 | 2025-11-11 |
| E-1083 | FCC Slurry Cooler | FCC | 2 | 20268 | 21.8 | 99.893 | 2025-09-09 |
| P-1084 | FCC Feed Pump | FCC | 1 | 39264 | 4.2 | 99.989 | 2025-10-14 |
| P-1091 | DHT Feed Pump | Diesel Hydrotreater | 2 | 21528 | 15.8 | 99.927 | 2026-07-28 |
| VS-1092 | DHT Reactor | Diesel Hydrotreater | 4 | 10344 | 11.2 | 99.892 | 2026-01-27 |
| E-1093 | DHT Product Cooler | Diesel Hydrotreater | 6 | 6616 | 18.2 | 99.726 | - |
| C-1125 | Sour Gas Compressor | Sulfur Recovery | 6 | 7176 | 7.3 | 99.898 | 2022-11-08 |
| VS-1126 | Amine Contactor | Sulfur Recovery | 2 | 20688 | 6.2 | 99.970 | 2025-01-07 |
| P-1127 | Lean Amine Pump | Sulfur Recovery | 1 | 39696 | 20.9 | 99.947 | 2023-09-19 |
| F-1111 | SMR Furnace | Hydrogen | 4 | 11502 | 5.3 | 99.954 | 2024-01-23 |
| C-1112 | Hydrogen Compressor | Hydrogen | 1 | 44304 | 22.9 | 99.948 | 2022-01-18 |
| VS-1113 | PSA Vessel | Hydrogen | 5 | 8520 | 18.4 | 99.785 | 2023-06-13 |
| TK-1121 | Naphtha Tank | Product Storage | 6 | 7668 | 22.9 | 99.702 | 2024-07-23 |
| TK-1122 | Diesel Tank | Product Storage | 2 | 22368 | 22.8 | 99.898 | 2025-03-25 |
| TK-1123 | Jet Tank | Product Storage | 3 | 14480 | 20.8 | 99.857 | 2025-11-18 |
| P-1124 | Product Loading Pump | Product Storage | 5 | 8434 | 18.4 | 99.782 | 2022-10-11 |
| P-1131 | Cooling Water Pump A | Cooling Water | 1 | 46728 | 6.1 | 99.987 | 2023-10-24 |
| P-1132 | Cooling Water Pump B | Cooling Water | 3 | 15256 | 18.8 | 99.877 | 2025-01-21 |
| UT-1133 | Cooling Tower Cell | Cooling Water | 2 | 22404 | 17.4 | 99.922 | 2026-03-10 |
| F-1141 | Steam Boiler | Steam | 3 | 15576 | 14.9 | 99.904 | - |
| P-1142 | Boiler Feed Pump | Steam | 2 | 22884 | 13.4 | 99.941 | - |
| M-1143 | BFD Fan Motor | Steam | 1 | 44808 | 15.1 | 99.966 | 2025-02-18 |
| UT-1151 | Instrument Air Package | Utilities | 4 | 11682 | 4.8 | 99.959 | - |
| C-1152 | Plant Air Compressor | Utilities | 4 | 11322 | 22.5 | 99.802 | 2026-09-15 |
| UT-1161 | Flare Stack | Flare | 6 | 7788 | 16.7 | 99.786 | 2026-04-28 |
| VS-1162 | Flare KO Drum | Flare | 6 | 7548 | 4.2 | 99.944 | 2025-07-22 |
| P-1171 | Wastewater Lift Pump | Wastewater | 4 | 11682 | 12.1 | 99.897 | - |
| VS-1172 | API Separator | Wastewater | 5 | 9058 | 10.5 | 99.884 | 2024-02-20 |
| ESD-1181 | Fire & Gas Panel | Safety Systems | 2 | 23364 | 16.1 | 99.931 | 2023-08-01 |
| ESD-1182 | Emergency Shutdown Valve | Safety Systems | 4 | 11322 | 18.0 | 99.841 | 2026-05-05 |

### 13.3 Availability by area

| Area | Units | Failures | Mean MTBF (h) | Mean MTTR (h) | Mean availability % |
|---|---|---|---|---|---|
| Crude Receiving | 4 | 7 | 32409 | 17.3 | 99.931 |
| Crude Storage | 3 | 11 | 15363 | 8.6 | 99.939 |
| Desalter | 3 | 12 | 13958 | 8.7 | 99.930 |
| Crude Distillation | 6 | 21 | 20869 | 11.8 | 99.905 |
| Vacuum Distillation | 4 | 10 | 22602 | 17.8 | 99.913 |
| Naphtha Hydrotreater | 4 | 14 | 15526 | 15.7 | 99.868 |
| Catalytic Reforming | 3 | 9 | 16209 | 12.6 | 99.925 |
| FCC | 4 | 11 | 20561 | 14.4 | 99.894 |
| Diesel Hydrotreater | 3 | 12 | 12829 | 15.1 | 99.848 |
| Sulfur Recovery | 3 | 9 | 22520 | 11.5 | 99.938 |
| Hydrogen | 3 | 10 | 21442 | 15.5 | 99.896 |
| Product Storage | 4 | 16 | 13237 | 21.2 | 99.810 |
| Utilities | 2 | 8 | 11502 | 13.7 | 99.881 |
| Steam | 3 | 6 | 27756 | 14.5 | 99.937 |
| Cooling Water | 3 | 6 | 28129 | 14.1 | 99.929 |
| Flare | 2 | 12 | 7668 | 10.4 | 99.865 |
| Wastewater | 2 | 9 | 10370 | 11.3 | 99.891 |
| Safety Systems | 2 | 6 | 17343 | 17.1 | 99.886 |

### 13.4 Failure-mode frequency

| Mode id | Name | Occurrences | Share of failures |
|---|---|---|---|
| sensor_failure | Sensor failure | 1 | 0.5% |
| instrument_drift | Instrument drift | 1 | 0.5% |
| bearing_wear | Bearing wear | 19 | 10.1% |
| cavitation | Pump cavitation | 15 | 7.9% |
| bearing_overheat | Bearing overheating | 23 | 12.2% |
| valve_stuck | Valve failure (stuck) | 5 | 2.6% |
| seal_leak | Seal failure / oil leak | 17 | 9.0% |
| pressure_surge | Pressure surge | 15 | 7.9% |
| trip | Equipment trip | 27 | 14.3% |
| fouling | Heat exchanger fouling | 7 | 3.7% |
| overload | Motor overload | 2 | 1.1% |
| esd | Emergency shutdown | 2 | 1.1% |

### 13.5 Lowest-availability assets

| Tag | Name | Area | Failures | MTBF (h) | MTTR (h) | Availability % |
|---|---|---|---|---|---|---|
| TK-1121 | Naphtha Tank | Product Storage | 6 | 7668 | 22.9 | 99.702 |
| E-1093 | DHT Product Cooler | Diesel Hydrotreater | 6 | 6616 | 18.2 | 99.726 |
| V-1064 | Stripper Level Valve | Naphtha Hydrotreater | 5 | 8434 | 21.9 | 99.741 |
| P-1124 | Product Loading Pump | Product Storage | 5 | 8434 | 18.4 | 99.782 |
| P-1042 | Crude Charge Pump | Crude Distillation | 5 | 9202 | 19.9 | 99.784 |
| VS-1113 | PSA Vessel | Hydrogen | 5 | 8520 | 18.4 | 99.785 |
| UT-1161 | Flare Stack | Flare | 6 | 7788 | 16.7 | 99.786 |
| C-1082 | Main Air Blower | FCC | 5 | 8362 | 17.4 | 99.792 |
| V-1047 | Column Feed Valve | Crude Distillation | 6 | 6956 | 14.1 | 99.798 |
| C-1152 | Plant Air Compressor | Utilities | 4 | 11322 | 22.5 | 99.802 |

### 13.6 Reading

Across 58 units the record shows 189 corrective failures, a plant mean MTBF of 19154 hours and a mean MTTR of 14.2 hours. The spread between the best and worst unit is roughly an order of magnitude, which is normal for a plant where rotating machines, fired heaters and safety elements are counted the same way. The compressor train is not the least reliable block in the plant, but it is the block whose degradation is most observable: a 1x-dominant vibration trend gives weeks of warning, which is exactly why the C-3 anomaly was caught before the alarm limit rather than after it.

### 13.7 Area reliability commentary

The commentary below pairs each area's availability figures with its condition and maintenance record so that a high availability with a low health score (a degraded asset still running) can be told apart from a genuinely reliable area.

### 13.7.1 Crude Receiving

**Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

### 13.7.2 Crude Storage

**Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

### 13.7.3 Desalter

**Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

### 13.7.4 Crude Distillation

**Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

### 13.7.5 Vacuum Distillation

**Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

### 13.7.6 Naphtha Hydrotreater

**Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

### 13.7.7 Catalytic Reforming

**Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

### 13.7.8 FCC

**FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

### 13.7.9 Diesel Hydrotreater

**Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

### 13.7.10 Sulfur Recovery

**Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

### 13.7.11 Hydrogen

**Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

### 13.7.12 Product Storage

**Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

### 13.7.13 Utilities

**Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

### 13.7.14 Steam

**Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

### 13.7.15 Cooling Water

**Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

### 13.7.16 Flare

**Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

### 13.7.17 Wastewater

**Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

### 13.7.18 Safety Systems

**Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

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

## 18. Historical Anomalies

The anomaly register carries 48 tracked deviations, `A-04` through `A-51`, in date order. An anomaly is a measurement outside its learned trend that did not necessarily breach an alarm limit - the point of the register is to catch deviations before they become incidents. `A-51` is the current C-3 vibration anomaly.

| Anomaly | Date | Equipment | Area | Measurement | Magnitude vs baseline | Resolution |
|---|---|---|---|---|---|---|
| A-04 | 2021-07-09 | P-1061 | Naphtha Hydrotreater | current | 106.47 A against a 92.14 A baseline (+15%) | load rebalanced, driven equipment inspected |
| A-05 | 2021-08-17 | P-1132 | Cooling Water | position | 57.78 % against a 40.5 % baseline (+42%) | actuator overhauled, position loop recalibrated |
| A-06 | 2021-09-23 | V-1003 | Crude Receiving | vibration | 8.35 mm/s against a 6.04 mm/s baseline (+38%) | daily monitoring, corrective work order raised |
| A-07 | 2021-11-03 | C-1125 | Sulfur Recovery | pressure | 33.85 bar against a 28.48 bar baseline (+18%) | control valve stroked, relief path verified |
| A-08 | 2021-12-15 | P-1127 | Sulfur Recovery | power | 542.63 kW against a 433.86 kW baseline (+25%) | impeller wear assessed, duty re-rated |
| A-09 | 2022-01-24 | TK-1121 | Product Storage | leak | 0.68 0/1 against a 0.48 0/1 baseline (+41%) | seal replaced, detector reset and held at zero |
| A-10 | 2022-03-04 | V-1064 | Naphtha Hydrotreater | rpm | 9809.18 rpm against a 8698.26 rpm baseline (+12%) | speed governor returned to setpoint |
| A-11 | 2022-04-12 | UT-1133 | Cooling Water | power | 290.18 kW against a 201.96 kW baseline (+43%) | impeller wear assessed, duty re-rated |
| A-12 | 2022-05-22 | V-1047 | Crude Distillation | rpm | 8801.66 rpm against a 6114.12 rpm baseline (+43%) | speed governor returned to setpoint |
| A-13 | 2022-06-30 | P-1127 | Sulfur Recovery | flow | 122.84 m3/h against a 96.14 m3/h baseline (+27%) | strainer cleaned, upstream path restored |
| A-14 | 2022-08-09 | C-1071 | Catalytic Reforming | position | 109.3 % against a 77.43 % baseline (+41%) | actuator overhauled, position loop recalibrated |
| A-15 | 2022-09-21 | P-1127 | Sulfur Recovery | leak | 0.31 0/1 against a 0.24 0/1 baseline (+29%) | seal replaced, detector reset and held at zero |
| A-16 | 2022-10-31 | TK-1121 | Product Storage | level | 89.77 % against a 77.21 % baseline (+16%) | level loop moved to manual, drain or fill path corrected |
| A-17 | 2022-12-10 | F-1141 | Steam | vibration | 6.67 mm/s against a 5.11 mm/s baseline (+30%) | daily monitoring, corrective work order raised |
| A-18 | 2023-01-17 | COL-1044 | Crude Distillation | leak | 0.03 0/1 against a 0.02 0/1 baseline (+49%) | seal replaced, detector reset and held at zero |
| A-19 | 2023-02-28 | P-1002 | Crude Receiving | temperature | 85.77 degC against a 63.54 degC baseline (+34%) | loop checked, calibration or lubrication corrected |
| A-20 | 2023-04-09 | P-1124 | Product Storage | pressure | 19.68 bar against a 15.86 bar baseline (+24%) | control valve stroked, relief path verified |
| A-21 | 2023-05-19 | VS-1126 | Sulfur Recovery | temperature | 90 degC against a 69.86 degC baseline (+28%) | loop checked, calibration or lubrication corrected |
| A-22 | 2023-06-27 | TK-1102 | Crude Storage | rpm | 11607.31 rpm against a 8177.05 rpm baseline (+41%) | speed governor returned to setpoint |
| A-23 | 2023-08-06 | VS-1073 | Catalytic Reforming | pressure | 43.9 bar against a 31.76 bar baseline (+38%) | control valve stroked, relief path verified |
| A-24 | 2023-09-15 | P-1002 | Crude Receiving | leak | 0.04 0/1 against a 0.03 0/1 baseline (+33%) | seal replaced, detector reset and held at zero |
| A-25 | 2023-10-26 | P-1127 | Sulfur Recovery | flow | 105.94 m3/h against a 83.51 m3/h baseline (+26%) | strainer cleaned, upstream path restored |
| A-26 | 2023-12-03 | C-1112 | Hydrogen | position | 111.89 % against a 86.43 % baseline (+29%) | actuator overhauled, position loop recalibrated |
| A-27 | 2024-01-13 | VS-1062 | Naphtha Hydrotreater | position | 74.43 % against a 52.35 % baseline (+42%) | actuator overhauled, position loop recalibrated |
| A-28 | 2024-02-20 | UT-1161 | Flare | power | 399.72 kW against a 278.15 kW baseline (+43%) | impeller wear assessed, duty re-rated |
| A-29 | 2024-04-01 | VS-1172 | Wastewater | power | 108.91 kW against a 98.27 kW baseline (+10%) | impeller wear assessed, duty re-rated |
| A-30 | 2024-05-13 | ESD-1181 | Safety Systems | gas | 18.86 %LEL against a 15.93 %LEL baseline (+18%) | exclusion zone set, release isolated and detector reset |
| A-31 | 2024-06-20 | F-1111 | Hydrogen | flow | 211.8 m3/h against a 147.86 m3/h baseline (+43%) | strainer cleaned, upstream path restored |
| A-32 | 2024-08-01 | C-1152 | Utilities | vibration | 5.37 mm/s against a 4.86 mm/s baseline (+10%) | daily monitoring, corrective work order raised |
| A-33 | 2024-09-08 | C-1053 | Vacuum Distillation | flow | 119.99 m3/h against a 85.12 m3/h baseline (+40%) | strainer cleaned, upstream path restored |
| A-34 | 2024-10-18 | P-1001 | Crude Receiving | level | 74.67 % against a 55.34 % baseline (+34%) | level loop moved to manual, drain or fill path corrected |
| A-35 | 2024-11-27 | VS-1092 | Diesel Hydrotreater | temperature | 79.63 degC against a 70.25 degC baseline (+13%) | loop checked, calibration or lubrication corrected |
| A-36 | 2025-01-07 | TK-1122 | Product Storage | current | 156.66 A against a 136.49 A baseline (+14%) | load rebalanced, driven equipment inspected |
| A-37 | 2025-02-14 | C-1082 | FCC | level | 116.36 % against a 89.58 % baseline (+29%) | level loop moved to manual, drain or fill path corrected |
| A-38 | 2025-03-27 | P-1132 | Cooling Water | gas | 30.32 %LEL against a 26.11 %LEL baseline (+16%) | exclusion zone set, release isolated and detector reset |
| A-39 | 2025-05-06 | C-1053 | Vacuum Distillation | temperature | 115.46 degC against a 85.2 degC baseline (+35%) | loop checked, calibration or lubrication corrected |
| A-40 | 2025-06-14 | F-1072 | Catalytic Reforming | power | 359.71 kW against a 262.5 kW baseline (+37%) | impeller wear assessed, duty re-rated |
| A-41 | 2025-07-27 | VS-1172 | Wastewater | current | 99.97 A against a 69.48 A baseline (+43%) | load rebalanced, driven equipment inspected |
| A-42 | 2025-09-04 | P-1142 | Steam | rpm | 10729.11 rpm against a 7844.01 rpm baseline (+36%) | speed governor returned to setpoint |
| A-43 | 2025-10-13 | P-1051 | Vacuum Distillation | power | 398.75 kW against a 350.33 kW baseline (+13%) | impeller wear assessed, duty re-rated |
| A-44 | 2025-11-24 | TK-1123 | Product Storage | vibration | 6.79 mm/s against a 5.28 mm/s baseline (+28%) | daily monitoring, corrective work order raised |
| A-45 | 2026-01-01 | VS-1126 | Sulfur Recovery | pressure | 51.62 bar against a 37.51 bar baseline (+37%) | control valve stroked, relief path verified |
| A-46 | 2026-02-12 | VS-1172 | Wastewater | power | 108.97 kW against a 77.28 kW baseline (+41%) | impeller wear assessed, duty re-rated |
| A-47 | 2026-03-21 | C-1071 | Catalytic Reforming | pressure | 21.48 bar against a 17.86 bar baseline (+20%) | control valve stroked, relief path verified |
| A-48 | 2026-05-03 | E-1045 | Crude Distillation | leak | 0.46 0/1 against a 0.35 0/1 baseline (+31%) | seal replaced, detector reset and held at zero |
| A-49 | 2026-06-11 | P-1001 | Crude Receiving | gas | 51.86 %LEL against a 40.72 %LEL baseline (+27%) | exclusion zone set, release isolated and detector reset |
| A-50 | 2026-07-19 | P-1171 | Wastewater | power | 189.54 kW against a 158.24 kW baseline (+19%) | impeller wear assessed, duty re-rated |
| A-51 | 2026-09-06 | C-1071 | Catalytic Reforming | vibration | 6.8 mm/s against a 5.7 mm/s learned baseline and a 5.8 mm/s 90-day rolling baseline (+18%) | IR-204 survey, daily monitoring, WO-8852 raised pending APR-231 outage approval |

### 18.1 Notable anomalies

**A-38 - P-1132, 2025-03-27 (gas).** Detected by area gas concentration; no critical alarm active at detection. Resolution: exclusion zone set, release isolated and detector reset

**A-39 - C-1053, 2025-05-06 (temperature).** Detected by bearing or outlet temperature; no critical alarm active at detection. Resolution: loop checked, calibration or lubrication corrected

**A-40 - F-1072, 2025-06-14 (power).** Detected by shaft power; no critical alarm active at detection. Resolution: impeller wear assessed, duty re-rated

**A-41 - VS-1172, 2025-07-27 (current).** Detected by motor current; no critical alarm active at detection. Resolution: load rebalanced, driven equipment inspected

**A-42 - P-1142, 2025-09-04 (rpm).** Detected by machine speed; no critical alarm active at detection. Resolution: speed governor returned to setpoint

**A-43 - P-1051, 2025-10-13 (power).** Detected by shaft power; no critical alarm active at detection. Resolution: impeller wear assessed, duty re-rated

**A-44 - TK-1123, 2025-11-24 (vibration).** Detected by overall vibration; no critical alarm active at detection. Resolution: daily monitoring, corrective work order raised

**A-45 - VS-1126, 2026-01-01 (pressure).** Detected by discharge or header pressure; no critical alarm active at detection. Resolution: control valve stroked, relief path verified

**A-46 - VS-1172, 2026-02-12 (power).** Detected by shaft power; no critical alarm active at detection. Resolution: impeller wear assessed, duty re-rated

**A-47 - C-1071, 2026-03-21 (pressure).** Detected by discharge or header pressure; no critical alarm active at detection. Resolution: control valve stroked, relief path verified

**A-48 - E-1045, 2026-05-03 (leak).** Detected by latched leak detector; no critical alarm active at detection. Resolution: seal replaced, detector reset and held at zero

**A-49 - P-1001, 2026-06-11 (gas).** Detected by area gas concentration; no critical alarm active at detection. Resolution: exclusion zone set, release isolated and detector reset

**A-50 - P-1171, 2026-07-19 (power).** Detected by shaft power; no critical alarm active at detection. Resolution: impeller wear assessed, duty re-rated

**A-51 - C-1071, 2026-09-06 (vibration).** Energy concentrated at 1x running speed on the drive-end bearing housing with bearing-housing temperature at 79 degC against a 68 degC baseline. Resolution: IR-204 survey, daily monitoring, WO-8852 raised pending APR-231 outage approval

### 18.2 Anomalies by measurement

| Measurement | Anomalies |
|---|---|
| power | 8 |
| vibration | 5 |
| pressure | 5 |
| leak | 5 |
| position | 4 |
| rpm | 4 |
| flow | 4 |
| temperature | 4 |
| current | 3 |
| level | 3 |
| gas | 3 |

### 18.3 Anomalies by area

| Area | Anomalies |
|---|---|
| Sulfur Recovery | 7 |
| Crude Receiving | 5 |
| Product Storage | 5 |
| Catalytic Reforming | 5 |
| Wastewater | 4 |
| Naphtha Hydrotreater | 3 |
| Cooling Water | 3 |
| Crude Distillation | 3 |
| Vacuum Distillation | 3 |
| Steam | 2 |
| Hydrogen | 2 |
| Crude Storage | 1 |
| Flare | 1 |
| Safety Systems | 1 |
| Utilities | 1 |
| Diesel Hydrotreater | 1 |
| FCC | 1 |

## 19. Maintenance Interventions

This section is the intervention register: the corrective events and the pinned console-narrative events, with duration and production impact. Preventive work is registered in Section 7 and is not repeated here. **131 interventions** are recorded.

| ME id | Date | Equipment | WO | Kind | Duration (h) | Production impact | Outcome |
|---|---|---|---|---|---|---|---|
| ME-003 | 2021-06-15 | C-1053 | WO-4102 | compressor | 30.2 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-009 | 2021-07-27 | F-1072 | WO-4108 | furnace | 5.4 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-010 | 2021-08-03 | P-1091 | WO-4109 | pump | 3.5 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-011 | 2021-08-10 | P-1124 | WO-4110 | pump | 8.0 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-020 | 2021-10-12 | P-1131 | WO-4119 | pump | 6.8 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-021 | 2021-10-19 | V-1103 | WO-4120 | valve | 21.2 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-023 | 2021-11-02 | P-1042 | WO-4122 | pump | 26.2 | short controlled stop | Temporary repair applied, follow-up work order raised |
| ME-025 | 2021-11-16 | TK-1121 | WO-4124 | tank | 3.0 | brief rate reduction | Check completed inside tolerance, next interval retained |
| ME-027 | 2021-11-30 | P-1124 | WO-4126 | pump | 12.0 | brief rate reduction | Temporary repair applied, follow-up work order raised |
| ME-028 | 2021-12-07 | UT-1161 | WO-4127 | utility | 14.7 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-032 | 2022-01-04 | P-1084 | WO-4700 | pump | 10.4 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-033 | 2022-01-11 | P-1001 | WO-4701 | pump | 3.1 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-034 | 2022-01-18 | C-1112 | WO-4702 | compressor | 27.4 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-035 | 2022-01-25 | TK-1102 | WO-4703 | tank | 19.9 | short controlled stop | Deviation cleared after adjustment, trend review scheduled |
| ME-036 | 2022-02-01 | P-1084 | WO-4704 | pump | 5.7 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-038 | 2022-02-15 | E-1083 | WO-4706 | exchanger | 3.5 | brief rate reduction | Fault corrected, equipment returned to service inside the normal band |
| ME-043 | 2022-03-22 | C-1152 | WO-4711 | compressor | 18.9 | none - duty covered by spare | Temporary repair applied, follow-up work order raised |
| ME-045 | 2022-04-05 | UT-1161 | WO-4713 | utility | 18.2 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-050 | 2022-05-10 | VS-1126 | WO-4718 | vessel | 27.0 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-053 | 2022-05-31 | P-1202 | WO-4721 | pump | 23.3 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-054 | 2022-06-07 | P-1042 | WO-4722 | pump | 19.5 | short controlled stop | Deviation cleared after adjustment, trend review scheduled |
| ME-055 | 2022-06-14 | C-1071 | WO-2417 | compressor | 9.1 | short controlled stop | No findings, next inspection interval retained |
| ME-059 | 2022-07-12 | TK-1102 | WO-4726 | tank | 10.9 | none - duty covered by spare | Component replaced, post-work survey inside the normal band |
| ME-060 | 2022-07-19 | TK-1102 | WO-4727 | tank | 4.6 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-061 | 2022-07-26 | C-1125 | WO-4728 | compressor | 3.3 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-063 | 2022-08-09 | P-1084 | WO-4730 | pump | 18.3 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-064 | 2022-08-16 | VS-1113 | WO-4731 | vessel | 17.0 | short controlled stop | Component replaced, post-work survey inside the normal band |
| ME-066 | 2022-08-30 | VS-1046 | WO-4733 | vessel | 5.0 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-068 | 2022-09-13 | VS-1073 | WO-4735 | vessel | 11.1 | brief rate reduction | Temporary repair applied, follow-up work order raised |
| ME-070 | 2022-09-27 | C-1125 | WO-4737 | compressor | 9.9 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-071 | 2022-10-04 | COL-1052 | WO-4738 | column | 6.2 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-072 | 2022-10-11 | P-1124 | WO-4739 | pump | 11.6 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-073 | 2022-10-18 | P-1132 | WO-4740 | pump | 31.6 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-074 | 2022-10-25 | P-1127 | WO-4741 | pump | 16.2 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-075 | 2022-11-01 | V-1047 | WO-4742 | valve | 7.5 | localised unit slowdown | Check completed inside tolerance, next interval retained |
| ME-076 | 2022-11-08 | C-1125 | WO-4743 | compressor | 6.8 | short controlled stop | Component replaced, post-work survey inside the normal band |
| ME-078 | 2022-11-22 | C-1053 | WO-4745 | compressor | 6.5 | none - line isolated | Component replaced, post-work survey inside the normal band |
| ME-081 | 2022-12-13 | P-1051 | WO-4748 | pump | 5.1 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-083 | 2022-12-27 | P-1091 | WO-4750 | pump | 18.0 | short controlled stop | Temporary repair applied, follow-up work order raised |
| ME-085 | 2023-01-10 | V-1203 | WO-5201 | valve | 29.4 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-087 | 2023-01-24 | E-1045 | WO-5203 | exchanger | 24.8 | none - line isolated | Deviation cleared after adjustment, trend review scheduled |
| ME-088 | 2023-01-31 | TK-1123 | WO-5204 | tank | 6.1 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-090 | 2023-02-14 | VS-1092 | WO-5206 | vessel | 3.3 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-091 | 2023-02-21 | VS-1113 | WO-5207 | vessel | 29.6 | brief rate reduction | Fault corrected, equipment returned to service inside the normal band |
| ME-096 | 2023-03-28 | P-1202 | WO-5212 | pump | 23.4 | localised unit slowdown | Fault corrected, equipment returned to service inside the normal band |
| ME-100 | 2023-04-25 | V-1047 | WO-5216 | valve | 18.6 | none - line isolated | Check completed inside tolerance, next interval retained |
| ME-102 | 2023-05-09 | P-1002 | WO-5218 | pump | 6.9 | short controlled stop | Component replaced, post-work survey inside the normal band |
| ME-103 | 2023-05-16 | E-1083 | WO-5219 | exchanger | 29.5 | short controlled stop | Component replaced, post-work survey inside the normal band |
| ME-104 | 2023-05-23 | UT-1161 | WO-5220 | utility | 13.9 | short controlled stop | Deviation cleared after adjustment, trend review scheduled |
| ME-105 | 2023-05-30 | P-1127 | WO-5221 | pump | 18.6 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-106 | 2023-06-06 | C-1053 | WO-5222 | compressor | 18.0 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-107 | 2023-06-13 | VS-1113 | WO-5223 | vessel | 11.9 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-114 | 2023-08-01 | ESD-1181 | WO-5230 | safety | 25.1 | none - duty covered by spare | Component replaced, post-work survey inside the normal band |
| ME-117 | 2023-08-22 | C-1082 | WO-5233 | compressor | 31.3 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-121 | 2023-09-19 | P-1127 | WO-5237 | pump | 7.5 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-123 | 2023-10-03 | V-1103 | WO-5239 | valve | 30.4 | none - line isolated | Component replaced, post-work survey inside the normal band |
| ME-125 | 2023-10-17 | COL-1052 | WO-5241 | column | 19.0 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-126 | 2023-10-24 | P-1131 | WO-5242 | pump | 19.7 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-128 | 2023-11-07 | P-1001 | WO-5244 | pump | 16.5 | none - duty covered by spare | Component replaced, post-work survey inside the normal band |
| ME-130 | 2023-11-21 | E-1083 | WO-5246 | exchanger | 9.4 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-134 | 2023-12-19 | ESD-1182 | WO-5250 | safety | 12.4 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-137 | 2024-01-09 | V-1103 | WO-5701 | valve | 26.6 | localised unit slowdown | Fault corrected, equipment returned to service inside the normal band |
| ME-139 | 2024-01-23 | F-1111 | WO-5703 | furnace | 23.5 | brief rate reduction | Temporary repair applied, follow-up work order raised |
| ME-140 | 2024-01-30 | COL-1044 | WO-5704 | column | 18.3 | brief rate reduction | Deviation cleared after adjustment, trend review scheduled |
| ME-141 | 2024-02-06 | V-1103 | WO-5705 | valve | 8.9 | none - line isolated | Deviation cleared after adjustment, trend review scheduled |
| ME-143 | 2024-02-20 | VS-1172 | WO-5707 | vessel | 15.7 | none - line isolated | Component replaced, post-work survey inside the normal band |
| ME-145 | 2024-03-05 | TK-1122 | WO-5709 | tank | 9.0 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-148 | 2024-03-26 | E-1063 | WO-5712 | exchanger | 27.4 | none - line isolated | No findings, next inspection interval retained |
| ME-152 | 2024-04-23 | TK-1121 | WO-5716 | tank | 11.5 | short controlled stop | Consumable renewed, condition confirmed normal |
| ME-154 | 2024-05-07 | P-1061 | WO-5718 | pump | 8.9 | none - line isolated | Deviation cleared after adjustment, trend review scheduled |
| ME-155 | 2024-05-14 | TK-1101 | WO-5719 | tank | 11.4 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-156 | 2024-05-21 | P-1061 | WO-5720 | pump | 25.7 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-157 | 2024-05-28 | P-1084 | WO-5721 | pump | 15.4 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-165 | 2024-07-23 | TK-1121 | WO-5729 | tank | 3.7 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-168 | 2024-08-13 | P-1061 | WO-5732 | pump | 6.6 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-179 | 2024-10-29 | E-1063 | WO-5743 | exchanger | 12.1 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-184 | 2024-12-03 | COL-1052 | WO-5748 | column | 16.4 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-186 | 2024-12-17 | E-1083 | WO-5750 | exchanger | 24.6 | none - line isolated | Fault corrected, equipment returned to service inside the normal band |
| ME-187 | 2024-12-24 | VS-1062 | WO-5751 | vessel | 22.2 | brief rate reduction | Deviation cleared after adjustment, trend review scheduled |
| ME-189 | 2025-01-07 | VS-1126 | WO-6100 | vessel | 15.7 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-190 | 2025-01-14 | V-1047 | WO-6101 | valve | 24.9 | short controlled stop | Consumable renewed, condition confirmed normal |
| ME-191 | 2025-01-21 | P-1132 | WO-6102 | pump | 4.6 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-195 | 2025-02-18 | M-1143 | WO-6106 | motor | 27.4 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-196 | 2025-02-25 | C-1152 | WO-6107 | compressor | 6.4 | short controlled stop | Component replaced, post-work survey inside the normal band |
| ME-198 | 2025-03-16 | C-1071 | WO-6120 | compressor | 27.6 | localised unit slowdown | Bearing replaced with OEM spare, alignment verified, re-baselined at 5.69 mm/s |
| ME-200 | 2025-03-25 | TK-1122 | WO-6110 | tank | 15.6 | localised unit slowdown | Fault corrected, equipment returned to service inside the normal band |
| ME-201 | 2025-04-01 | V-1203 | WO-6111 | valve | 28.7 | none - duty covered by spare | Fault corrected, equipment returned to service inside the normal band |
| ME-207 | 2025-05-13 | TK-1121 | WO-6117 | tank | 15.1 | localised unit slowdown | No findings, next inspection interval retained |
| ME-208 | 2025-05-20 | VS-1046 | WO-6118 | vessel | 31.4 | short controlled stop | Temporary repair applied, follow-up work order raised |
| ME-211 | 2025-06-10 | VS-1073 | WO-6122 | vessel | 26.9 | short controlled stop | Deviation cleared after adjustment, trend review scheduled |
| ME-212 | 2025-06-17 | P-1084 | WO-6123 | pump | 13.6 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-213 | 2025-06-24 | P-1202 | WO-6124 | pump | 6.5 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-214 | 2025-07-01 | TK-1123 | WO-6125 | tank | 19.2 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-217 | 2025-07-22 | VS-1162 | WO-6128 | vessel | 9.4 | brief rate reduction | Component replaced, post-work survey inside the normal band |
| ME-218 | 2025-07-29 | P-1202 | WO-6129 | pump | 14.2 | localised unit slowdown | Deviation cleared after adjustment, trend review scheduled |
| ME-219 | 2025-08-05 | E-1063 | WO-6130 | exchanger | 26.0 | none - duty covered by spare | Consumable renewed, condition confirmed normal |
| ME-223 | 2025-09-02 | P-1042 | WO-6134 | pump | 24.2 | none - line isolated | No findings, next inspection interval retained |
| ME-224 | 2025-09-09 | E-1083 | WO-6135 | exchanger | 18.0 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-225 | 2025-09-16 | V-1047 | WO-6136 | valve | 15.7 | short controlled stop | No findings, next inspection interval retained |
| ME-229 | 2025-10-14 | P-1084 | WO-6140 | pump | 16.0 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-231 | 2025-10-28 | E-1063 | WO-6142 | exchanger | 14.6 | brief rate reduction | Minor wear noted, no immediate action |
| ME-232 | 2025-11-02 | C-1071 | WO-2417 | compressor | 5.5 | brief rate reduction | Coupling offset 0.06 mm within 0.10 mm tolerance; no correction |
| ME-234 | 2025-11-11 | C-1082 | WO-6144 | compressor | 8.0 | localised unit slowdown | Temporary repair applied, follow-up work order raised |
| ME-235 | 2025-11-18 | TK-1123 | WO-6145 | tank | 27.7 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-236 | 2025-11-25 | TK-1102 | WO-6146 | tank | 26.3 | brief rate reduction | Deviation cleared after adjustment, trend review scheduled |
| ME-237 | 2025-12-02 | C-1071 | WO-6147 | compressor | 12.3 | brief rate reduction | Deviation cleared after adjustment, trend review scheduled |
| ME-239 | 2025-12-16 | P-1061 | WO-6149 | pump | 4.6 | short controlled stop | Fault corrected, equipment returned to service inside the normal band |
| ME-240 | 2025-12-23 | P-1091 | WO-6150 | pump | 13.3 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-245 | 2026-01-27 | VS-1092 | WO-8603 | vessel | 6.0 | none - duty covered by spare | Deviation cleared after adjustment, trend review scheduled |
| ME-246 | 2026-02-03 | P-1042 | WO-8604 | pump | 10.4 | none - line isolated | Component replaced, post-work survey inside the normal band |
| ME-247 | 2026-02-10 | C-1071 | WO-8605 | compressor | 24.4 | short controlled stop | No findings, next inspection interval retained |
| ME-248 | 2026-02-17 | TK-1101 | WO-8606 | tank | 9.3 | localised unit slowdown | Fault corrected, equipment returned to service inside the normal band |
| ME-249 | 2026-02-24 | P-1202 | WO-8607 | pump | 22.1 | none - duty covered by spare | Temporary repair applied, follow-up work order raised |
| ME-251 | 2026-03-10 | UT-1133 | WO-8609 | utility | 22.6 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-252 | 2026-03-17 | C-1071 | WO-8610 | compressor | 3.7 | brief rate reduction | No findings, next inspection interval retained |
| ME-254 | 2026-03-31 | V-1003 | WO-8612 | valve | 27.9 | brief rate reduction | Deviation cleared after adjustment, trend review scheduled |
| ME-258 | 2026-04-28 | UT-1161 | WO-8616 | utility | 5.6 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-259 | 2026-05-05 | ESD-1182 | WO-8617 | safety | 20.3 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-261 | 2026-05-19 | P-1042 | WO-8619 | pump | 30.8 | short controlled stop | Minor wear noted, no immediate action |
| ME-263 | 2026-06-02 | C-1071 | WO-8621 | compressor | 20.5 | none - line isolated | No findings, next inspection interval retained |
| ME-266 | 2026-06-23 | VS-1062 | WO-8624 | vessel | 20.3 | short controlled stop | Temporary repair applied, follow-up work order raised |
| ME-267 | 2026-06-30 | P-1042 | WO-8625 | pump | 29.8 | short controlled stop | No findings, next inspection interval retained |
| ME-271 | 2026-07-28 | P-1091 | WO-8629 | pump | 10.0 | none - duty covered by spare | Component replaced, post-work survey inside the normal band |
| ME-273 | 2026-08-11 | V-1047 | WO-8631 | valve | 31.3 | short controlled stop | Temporary repair applied, follow-up work order raised |
| ME-274 | 2026-08-18 | TK-1121 | WO-8802 | tank | 24.1 | none - line isolated | No findings, next inspection interval retained |
| ME-276 | 2026-08-26 | E-1063 | WO-8810 | exchanger | 16.1 | none - line isolated | Check completed inside tolerance, next interval retained |
| ME-278 | 2026-09-03 | V-1047 | WO-8837 | valve | 16.6 | none - duty covered by spare | Temporary repair applied, follow-up work order raised |
| ME-279 | 2026-09-04 | P-1042 | WO-8841 | pump | 25.3 | none - line isolated | Temporary repair applied, follow-up work order raised |
| ME-280 | 2026-09-07 | C-1071 | WO-8852 | compressor | 23.2 | brief rate reduction | Open, pending approval APR-231 |
| ME-282 | 2026-09-15 | C-1152 | WO-8635 | compressor | 14.3 | localised unit slowdown | Component replaced, post-work survey inside the normal band |
| ME-283 | 2026-09-22 | E-1045 | WO-8636 | exchanger | 3.6 | brief rate reduction | Temporary repair applied, follow-up work order raised |

### 19.1 Intervention classes

Interventions fall into four classes: **instrument** (transmitter replacement, calibration and loop repair), **mechanical rotating** (bearing, seal, coupling and impeller work), **static** (valve actuator, exchanger bundle, vessel internals) and **electrical** (motor and drive). Mechanical rotating work consumes the most downtime per event; instrument work is the most frequent but the shortest. That asymmetry is the reason the plant carries redundant pressure on every seven-instrument pump block: it converts the most frequent failure class into a no-stop event.

### 19.2 The three anchor interventions

* **ME-198 (2025-03-16, C-3 / C-1071, WO-6120).** Drive-end bearing replacement. Outer-race spalling on two rolling elements and lube-oil varnish on the cage. Post-repair vibration 5.4 mm/s; re-baselined at 5.69 mm/s.
* **ME-212 (2025-11-02, C-3 / C-1071, WO-2417).** Hot alignment check after six hours of steady operation. Coupling offset 0.06 mm against a 0.10 mm tolerance, angular 0.02 mm/100 mm against 0.05. Soft-foot check passed. No correction.
* **WO-8852 (2026-09-07, C-3 / C-1071).** Drive-end bearing inspection raised from IR-204, pending outage approval APR-231.

## 20. Current Operational Status

Status as of **2026-09-30**. All 58 registered units are on line and reporting. Two carry a degraded condition: C-1071 (C-3) at WARNING and P-1042 at WARNING. No unit is tripped, and no area is isolated.

### 20.1 Register status

| Tag | Name | Area | Status | Health | Next maintenance |
|---|---|---|---|---|---|
| P-1001 | Offloading Pump A | Crude Receiving | NORMAL | 87/100 | 2026-08-02 |
| P-1002 | Offloading Pump B | Crude Receiving | NORMAL | 89/100 | 2027-03-04 |
| V-1003 | Receiving Header Valve | Crude Receiving | NORMAL | 88/100 | 2026-08-03 |
| E-1004 | Crude Preheater | Crude Receiving | NORMAL | 87/100 | 2026-11-02 |
| TK-1101 | Crude Tank 1 | Crude Storage | NORMAL | 88/100 | 2026-12-19 |
| TK-1102 | Crude Tank 2 | Crude Storage | NORMAL | 93/100 | 2027-07-23 |
| V-1103 | Tank Outlet Valve | Crude Storage | NORMAL | 88/100 | 2026-12-22 |
| VS-1201 | Desalter Vessel | Desalter | NORMAL | 88/100 | 2026-08-13 |
| P-1202 | Desalter Water Pump | Desalter | NORMAL | 90/100 | 2027-03-15 |
| V-1203 | Brine Outlet Valve | Desalter | NORMAL | 88/100 | 2026-08-14 |
| P-1042 | Crude Charge Pump | Crude Distillation | WARNING | 84/100 | 2027-03-17 |
| F-1043 | Crude Charge Heater | Crude Distillation | NORMAL | 86/100 | 2026-08-16 |
| COL-1044 | Atmospheric Column | Crude Distillation | NORMAL | 90/100 | 2026-11-15 |
| E-1045 | Overhead Condenser | Crude Distillation | NORMAL | 94/100 | 2027-06-20 |
| VS-1046 | Reflux Drum | Crude Distillation | NORMAL | 88/100 | 2026-11-18 |
| V-1047 | Column Feed Valve | Crude Distillation | NORMAL | 85/100 | 2027-02-18 |
| P-1051 | VDU Feed Pump | Vacuum Distillation | NORMAL | 88/100 | 2026-10-23 |
| COL-1052 | Vacuum Column | Vacuum Distillation | NORMAL | 90/100 | 2027-05-27 |
| C-1053 | Vacuum Ejector Compressor | Vacuum Distillation | NORMAL | 86/100 | 2026-09-29 |
| E-1054 | Vacuum Resid Cooler | Vacuum Distillation | NORMAL | 86/100 | 2026-12-29 |
| P-1061 | NHT Feed Pump | Naphtha Hydrotreater | NORMAL | 88/100 | 2026-12-06 |
| VS-1062 | NHT Reactor | Naphtha Hydrotreater | NORMAL | 92/100 | 2027-07-10 |
| E-1063 | NHT Effluent Cooler | Naphtha Hydrotreater | NORMAL | 84/100 | 2026-12-09 |
| V-1064 | Stripper Level Valve | Naphtha Hydrotreater | NORMAL | 89/100 | 2026-07-11 |
| C-1071 | Reformer Recycle Compressor | Catalytic Reforming | WARNING | 82/100 | 2027-02-15 |
| F-1072 | Reformer Charge Heater | Catalytic Reforming | NORMAL | 88/100 | 2027-01-20 |
| VS-1073 | Reformer Separator | Catalytic Reforming | NORMAL | 85/100 | 2026-06-21 |
| VS-1081 | FCC Reactor | FCC | NORMAL | 86/100 | 2026-08-01 |
| C-1082 | Main Air Blower | FCC | NORMAL | 94/100 | 2027-03-03 |
| E-1083 | FCC Slurry Cooler | FCC | NORMAL | 85/100 | 2026-08-02 |
| P-1084 | FCC Feed Pump | FCC | NORMAL | 88/100 | 2026-11-01 |
| P-1091 | DHT Feed Pump | Diesel Hydrotreater | NORMAL | 90/100 | 2026-10-09 |
| VS-1092 | DHT Reactor | Diesel Hydrotreater | NORMAL | 91/100 | 2027-05-13 |
| E-1093 | DHT Product Cooler | Diesel Hydrotreater | NORMAL | 87/100 | 2026-10-12 |
| C-1125 | Sour Gas Compressor | Sulfur Recovery | NORMAL | 92/100 | 2027-06-19 |
| VS-1126 | Amine Contactor | Sulfur Recovery | NORMAL | 84/100 | 2026-11-17 |
| P-1127 | Lean Amine Pump | Sulfur Recovery | NORMAL | 87/100 | 2027-02-17 |
| F-1111 | SMR Furnace | Hydrogen | NORMAL | 86/100 | 2027-02-01 |
| C-1112 | Hydrogen Compressor | Hydrogen | NORMAL | 92/100 | 2027-01-06 |
| VS-1113 | PSA Vessel | Hydrogen | NORMAL | 88/100 | 2026-06-07 |
| TK-1121 | Naphtha Tank | Product Storage | NORMAL | 89/100 | 2026-08-14 |
| TK-1122 | Diesel Tank | Product Storage | NORMAL | 91/100 | 2027-03-16 |
| TK-1123 | Jet Tank | Product Storage | NORMAL | 87/100 | 2026-08-15 |
| P-1124 | Product Loading Pump | Product Storage | NORMAL | 91/100 | 2026-11-14 |
| P-1131 | Cooling Water Pump A | Cooling Water | NORMAL | 91/100 | 2026-10-22 |
| P-1132 | Cooling Water Pump B | Cooling Water | NORMAL | 90/100 | 2027-05-26 |
| UT-1133 | Cooling Tower Cell | Cooling Water | NORMAL | 87/100 | 2026-10-25 |
| F-1141 | Steam Boiler | Steam | NORMAL | 88/100 | 2026-12-05 |
| P-1142 | Boiler Feed Pump | Steam | NORMAL | 89/100 | 2027-07-09 |
| M-1143 | BFD Fan Motor | Steam | NORMAL | 83/100 | 2026-12-08 |
| UT-1151 | Instrument Air Package | Utilities | NORMAL | 88/100 | 2027-02-14 |
| C-1152 | Plant Air Compressor | Utilities | NORMAL | 91/100 | 2027-01-19 |
| UT-1161 | Flare Stack | Flare | NORMAL | 90/100 | 2026-07-31 |
| VS-1162 | Flare KO Drum | Flare | NORMAL | 91/100 | 2027-03-02 |
| P-1171 | Wastewater Lift Pump | Wastewater | NORMAL | 91/100 | 2026-10-08 |
| VS-1172 | API Separator | Wastewater | NORMAL | 89/100 | 2027-05-12 |
| ESD-1181 | Fire & Gas Panel | Safety Systems | NORMAL | 88/100 | 2026-12-18 |
| ESD-1182 | Emergency Shutdown Valve | Safety Systems | NORMAL | 90/100 | 2027-07-22 |

### 20.2 Overlay asset status

| Asset | Name | Signal | Value | Unit | State |
|---|---|---|---|---|---|
| C-3 | Recycle Gas Compressor | vibration_overall | 6.8 | mm/s | warning |
| C-3 | Recycle Gas Compressor | bearing_temp_de | 79 | degC | warning |
| C-3 | Recycle Gas Compressor | discharge_pressure | 42.1 | bar | normal |
| P-1042 | Feed Charge Pump | discharge_pressure | 18.5 | bar | exceeded |
| V-2210 | Product Separator Vessel | level | 87 | % | exceeded |
| T-118 | Intermediate Storage Tank | level | 54 | % | normal |
| E-340 | Feed/Effluent Heat Exchanger | delta_p | 0.42 | bar | normal |
| P-2051 | Product Transfer Pump | vibration_overall | 0 | mm/s | offline |

### 20.3 Active and recent work orders

| WO | Equipment | Scope | Priority | Status | Due | Note |
|---|---|---|---|---|---|---|
| WO-8852 | C-1071 (C-3) | C-3 drive-end bearing inspection | high | open | 2026-09-18 | pending approval APR-231 |
| WO-8841 | P-1042 | P-1042 discharge pressure investigation | medium | in_progress | 2026-09-12 | relief path and impeller wear check |
| WO-8837 | V-1047 (V-2210) | V-2210 high level alarm response | critical | in_progress | 2026-09-10 | level loop verified and drained |
| WO-8810 | E-1063 (E-340) | E-340 fouling trend review | low | open | 2026-09-30 | quarterly delta-P review; no action expected |
| WO-8802 | TK-1121 (T-118) | T-118 external visual inspection | low | completed | 2026-08-30 | no findings |
| WO-2417 | C-1071 (C-3) | C-3 coupling alignment re-execution | medium | completed | - | offset 0.06 mm within tolerance |

### 20.4 Active anomalies

One anomaly is live: **A-51**, C-1071 (C-3) vibration 18% above its learned baseline, opened 2026-09-06. A-50 and earlier anomalies are resolved and are closed in the register at Section 18.

### 20.5 Watch list

* **C-1071 (C-3)** - daily vibration monitoring until the amplitude stabilises or the bearing is inspected. Watch for the 7.1 mm/s alarm limit and the 85 degC bearing limit.
* **P-1042** - discharge pressure above the 17.0 bar operating limit. Watch FT-1042 against the redundant pressure pair to separate downstream restriction from impeller wear.
* **V-1047 (V-2210)** - high level excursion corrected; confirm the level loop holds after the drain and that no detector remains latched in the area.
* **E-1063 (E-340)** - delta-P 5% above clean reference; routine quarterly review only.
* **TK-1121 (T-118)** - no action; next external inspection on the register interval.

### 20.6 Area status

**Crude Receiving.** 4 units on line, status NORMAL across the area. **Crude Receiving.** 4 units, 19 instruments, carrying exchanger, pump, valve. The review period recorded 4 corrective and 11 preventive events here, with 7 modelled failures. Best-condition asset is P-1002 (Offloading Pump B, 89/100); lowest-condition asset is P-1001 (Offloading Pump A, 87/100). Most recent maintenance event: 2026-07-07.

**Crude Storage.** 3 units on line, status NORMAL across the area. **Crude Storage.** 3 units, 6 instruments, carrying tank, valve. The review period recorded 10 corrective and 8 preventive events here, with 11 modelled failures. Best-condition asset is TK-1102 (Crude Tank 2, 93/100); lowest-condition asset is TK-1101 (Crude Tank 1, 88/100). Most recent maintenance event: 2026-06-09.

**Desalter.** 3 units on line, status NORMAL across the area. **Desalter.** 3 units, 12 instruments, carrying pump, valve, vessel. The review period recorded 7 corrective and 5 preventive events here, with 12 modelled failures. Best-condition asset is P-1202 (Desalter Water Pump, 90/100); lowest-condition asset is VS-1201 (Desalter Vessel, 88/100). Most recent maintenance event: 2026-02-24.

**Crude Distillation.** 6 units on line, status WARNING on P-1042. **Crude Distillation.** 6 units, 21 instruments, carrying column, exchanger, furnace, pump, valve, vessel. The review period recorded 11 corrective and 18 preventive events here, with 21 modelled failures. Best-condition asset is E-1045 (Overhead Condenser, 94/100); lowest-condition asset is P-1042 (Crude Charge Pump, 84/100). Most recent maintenance event: 2026-09-22.

**Vacuum Distillation.** 4 units on line, status NORMAL across the area. **Vacuum Distillation.** 4 units, 18 instruments, carrying column, compressor, exchanger, pump. The review period recorded 7 corrective and 14 preventive events here, with 10 modelled failures. Best-condition asset is COL-1052 (Vacuum Column, 90/100); lowest-condition asset is C-1053 (Vacuum Ejector Compressor, 86/100). Most recent maintenance event: 2026-09-29.

**Naphtha Hydrotreater.** 4 units on line, status NORMAL across the area. **Naphtha Hydrotreater.** 4 units, 15 instruments, carrying exchanger, pump, valve, vessel. The review period recorded 7 corrective and 13 preventive events here, with 14 modelled failures. Best-condition asset is VS-1062 (NHT Reactor, 92/100); lowest-condition asset is E-1063 (NHT Effluent Cooler, 84/100). Most recent maintenance event: 2026-08-26.

**Catalytic Reforming.** 3 units on line, status WARNING on C-1071. **Catalytic Reforming.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 6 corrective and 9 preventive events here, with 9 modelled failures. Best-condition asset is F-1072 (Reformer Charge Heater, 88/100); lowest-condition asset is C-1071 (Reformer Recycle Compressor, 82/100). Most recent maintenance event: 2026-09-07.

**FCC.** 4 units on line, status NORMAL across the area. **FCC.** 4 units, 18 instruments, carrying compressor, exchanger, pump, vessel. The review period recorded 13 corrective and 10 preventive events here, with 11 modelled failures. Best-condition asset is C-1082 (Main Air Blower, 94/100); lowest-condition asset is E-1083 (FCC Slurry Cooler, 85/100). Most recent maintenance event: 2026-01-13.

**Diesel Hydrotreater.** 3 units on line, status NORMAL across the area. **Diesel Hydrotreater.** 3 units, 13 instruments, carrying exchanger, pump, vessel. The review period recorded 6 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1092 (DHT Reactor, 91/100); lowest-condition asset is E-1093 (DHT Product Cooler, 87/100). Most recent maintenance event: 2026-07-28.

**Sulfur Recovery.** 3 units on line, status NORMAL across the area. **Sulfur Recovery.** 3 units, 15 instruments, carrying compressor, pump, vessel. The review period recorded 8 corrective and 10 preventive events here, with 9 modelled failures. Best-condition asset is C-1125 (Sour Gas Compressor, 92/100); lowest-condition asset is VS-1126 (Amine Contactor, 84/100). Most recent maintenance event: 2026-09-01.

**Hydrogen.** 3 units on line, status NORMAL across the area. **Hydrogen.** 3 units, 11 instruments, carrying compressor, furnace, vessel. The review period recorded 5 corrective and 9 preventive events here, with 10 modelled failures. Best-condition asset is C-1112 (Hydrogen Compressor, 92/100); lowest-condition asset is F-1111 (SMR Furnace, 86/100). Most recent maintenance event: 2026-08-25.

**Product Storage.** 4 units on line, status NORMAL across the area. **Product Storage.** 4 units, 13 instruments, carrying pump, tank. The review period recorded 9 corrective and 11 preventive events here, with 16 modelled failures. Best-condition asset is TK-1122 (Diesel Tank, 91/100); lowest-condition asset is TK-1123 (Jet Tank, 87/100). Most recent maintenance event: 2026-08-18.

**Utilities.** 2 units on line, status NORMAL across the area. **Utilities.** 2 units, 6 instruments, carrying compressor, utility. The review period recorded 3 corrective and 8 preventive events here, with 8 modelled failures. Best-condition asset is C-1152 (Plant Air Compressor, 91/100); lowest-condition asset is UT-1151 (Instrument Air Package, 88/100). Most recent maintenance event: 2026-09-15.

**Steam.** 3 units on line, status NORMAL across the area. **Steam.** 3 units, 13 instruments, carrying furnace, motor, pump. The review period recorded 1 corrective and 9 preventive events here, with 6 modelled failures. Best-condition asset is P-1142 (Boiler Feed Pump, 89/100); lowest-condition asset is M-1143 (BFD Fan Motor, 83/100). Most recent maintenance event: 2026-06-16.

**Cooling Water.** 3 units on line, status NORMAL across the area. **Cooling Water.** 3 units, 15 instruments, carrying pump, utility. The review period recorded 5 corrective and 13 preventive events here, with 6 modelled failures. Best-condition asset is P-1131 (Cooling Water Pump A, 91/100); lowest-condition asset is UT-1133 (Cooling Tower Cell, 87/100). Most recent maintenance event: 2026-03-10.

**Flare.** 2 units on line, status NORMAL across the area. **Flare.** 2 units, 4 instruments, carrying utility, vessel. The review period recorded 5 corrective and 8 preventive events here, with 12 modelled failures. Best-condition asset is VS-1162 (Flare KO Drum, 91/100); lowest-condition asset is UT-1161 (Flare Stack, 90/100). Most recent maintenance event: 2026-08-04.

**Wastewater.** 2 units on line, status NORMAL across the area. **Wastewater.** 2 units, 10 instruments, carrying pump, vessel. The review period recorded 1 corrective and 6 preventive events here, with 9 modelled failures. Best-condition asset is P-1171 (Wastewater Lift Pump, 91/100); lowest-condition asset is VS-1172 (API Separator, 89/100). Most recent maintenance event: 2026-09-08.

**Safety Systems.** 2 units on line, status NORMAL across the area. **Safety Systems.** 2 units, 4 instruments, carrying safety. The review period recorded 3 corrective and 3 preventive events here, with 6 modelled failures. Best-condition asset is ESD-1182 (Emergency Shutdown Valve, 90/100); lowest-condition asset is ESD-1181 (Fire & Gas Panel, 88/100). Most recent maintenance event: 2026-05-05.

## 21. Lessons Learned

The programme produced sixteen standing lessons. Each is tied to evidence in this dossier rather than stated as a general principle.

### 21.1 Vibration responds to oil condition before it responds to load

The first C-3 vibration event (2022-11-18, A-19) reached 6.1 mm/s during a lube-oil temperature excursion and cleared after an oil flush with no mechanical work. Lube-oil condition was made a first-line check on every rotating vibration call-out.

### 21.2 A learned baseline beats a fixed alarm limit for early warning

C-3 was at 6.8 mm/s against a 7.1 mm/s alarm, which looks safe, but 18% above its own baseline. The learned baseline caught the deviation weeks before the alarm limit would have (IR-204, A-51).

### 21.3 Redundant pressure converts the most frequent failure into a no-stop event

Instrument faults are the most common event class. The A/B pressure pair on the seven-instrument pump blocks lets SOP-14.2 be executed without stopping the pump, as scenario `sc-sensor-failure` is designed to prove.

### 21.4 Keep the process limit separate from the transmitter envelope

P-1042's 17.0 bar alert threshold is deliberately narrower than the PT-1042A normal band of 17.76 to 19.24 bar. Conflating the two would either hide the excursion or trip the unit unnecessarily.

### 21.5 Alignment must be eliminated before bearing wear is assumed

The 2025-11-02 hot alignment check measured a 0.06 mm coupling offset against a 0.10 mm tolerance. That negative result is what justified attributing the residual trend to the bearing rather than to alignment.

### 21.6 Fouling is trended, not cleaned on instinct

E-340 at 5% over the clean reference recovers almost no duty if cleaned early; the quarterly delta-P review exists to make the decision to do nothing explicit and recorded (WO-8810).

### 21.7 An inspection that recommends no action is still a controlled record

WO-8802 on T-118 and WO-8810 on E-340 both expect no action. Recording the decision is what makes a later change visible.

### 21.8 Detectors are latched, not analogue

A detector reading zero is healthy. Treating it as an envelope violation produces false alarms; silencing a latched detector hides a real release. SOP-41.2 rev8 makes this explicit.

### 21.9 A second trip on the same fault damages the drive

SOP-18.3 rev4 forbids reset-and-restart without establishing the trip cause. The current-signature check distinguishes a mechanical load problem from an electrical fault before the drive is energised again.

### 21.10 Above 10% deviation, monitoring frequency is the control

SOP-07.3 rev4 section 4.2 raises monitoring to once per shift and requires a corrective work order within 72 hours. Frequency, not a tighter alarm, is what buys warning time.

### 21.11 Outage approval is a safety control, not paperwork

APR-231 gates the C-3 bearing outage because SOP-07.3 rev4 section 5 requires manager approval for an outage on criticality-high equipment.

### 21.12 Units can run degraded only with an explicit compensating measurement

OPS-03.2 rev4 permits continued operation with a failed instrument only when a validated alternate covers the same control objective and the condition is reviewed at shift handover.

### 21.13 Two unavailable measurements on one service means reduce rate

The escalation rule is measurable: two or more measurements on the same service unavailable, a latched detector in the area, or loss of the only downstream flow path.

### 21.14 Cavitation and impeller wear can look identical on discharge pressure

Both raise discharge pressure against falling or unstable flow. Check suction level and suction pressure before touching the pump (SOP-22.4 rev2).

### 21.15 Small anomalies are cheap; incident records are not

48 anomalies produced 36 incident or event records and a small number of interventions. The anomaly register is the cheapest part of the reliability programme.

### 21.16 Health scores and availability answer different questions

Health is a condition score derived from the register; availability is a time-based reliability figure. A unit can be healthy and unavailable, or degraded and available. Sections 4 and 13 must be read together.

## 22. Recommended Actions

The recommended actions below are concrete and prioritised. **P1** actions are required now and are tied to a live deviation; **P2** actions are required this quarter and protect a degraded or critical asset; **P3** actions are scheduled improvements. Every action names an equipment tag that resolves in this document, a rationale, an evidence reference and a target date. Target dates are forecast dates and may fall after the dossier cutoff of 2026-09-30; all historical records in this document do not.

| Priority | Equipment | Action | Rationale | Evidence | Target date |
|---|---|---|---|---|---|
| P1 | C-1071 (C-3) | Complete the drive-end bearing inspection at the first approved outage window and perform a hot alignment check before re-baselining. | Vibration is 18% above the learned baseline with 1x dominance and DE bearing temperature is 11 degC above baseline; both SOP-07.3 rev4 section 4.3 triggers are met. | IR-204; A-51; SOP-07.3 rev4 s.4.3; WO-8852 | 2026-10-04 |
| P1 | C-1071 (C-3) | Sustain once-per-shift vibration and bearing-temperature monitoring until the amplitude stabilises or the bearing is inspected. | The machine is inside the 7.1 mm/s alarm limit but outside the 10% deviation band; frequency is the only control that buys warning time. | SOP-07.3 rev4 s.4.2; IR-204 | 2026-09-30 |
| P1 | C-1071 (C-3) | Approve or reject outage approval APR-231 at the next maintenance-planning gate. | WO-8852 cannot be scheduled on criticality-high equipment without manager approval under SOP-07.3 rev4 section 5. | APR-231; WO-8852; SOP-07.3 rev4 s.5 | 2026-09-25 |
| P1 | P-1042 | Confirm suction conditions at the desalter and crude storage before any mechanical work, and trend FT-1042 against PT-1042A and PT-1042B. | Cavitation and impeller wear produce the same discharge-pressure signature; suction must be excluded first. | WO-8841; SOP-22.4 rev2; FT-1042 | 2026-09-20 |
| P1 | P-1042 | Verify the relief path and inspect impeller wear if the pressure excursion persists after suction is confirmed. | Discharge pressure is +14% above baseline against a 17.0 bar operating limit and the cause is not yet isolated. | WO-8841; PT-1042A | 2026-10-10 |
| P1 | V-1047 (V-2210) | Confirm the level loop holds after the drain and that no detector remains latched in the area. | The 87% level excursion breached the 80% setpoint; the incident may not be closed while a detector in the area is latched. | WO-8837; APR-218; SOP-41.2 rev8 | 2026-09-20 |
| P2 | C-1071 (C-3) | Sample and analyse lube oil for varnish and particle count before the bearing is opened. | The 2022 event and the 2025 bearing finding both implicated oil condition; a sample now separates an oil problem from a mechanical one. | IR-198; A-19; SOP-22.1 rev5 | 2026-10-01 |
| P2 | C-1071 (C-3) | Re-execute the anti-surge valve stroke test and capture the surge margin at current conditions. | A slow anti-surge valve changes the machine's surge behaviour and can masquerade as a process vibration source. | ME-212 record; V-1047 | 2026-10-15 |
| P2 | P-1042 | Calibrate PT-1042A and PT-1042B against a deadweight tester and confirm they agree within 2% of span. | The operating limit is only as good as the redundant pair; SOP-14.2 requires agreement within 2% of span. | SOP-14.2 rev6; PT-1042A; PT-1042B | 2026-10-12 |
| P2 | E-1063 (E-340) | Continue the quarterly delta-P trend review and add outlet temperature at constant flow as the primary duty-loss indicator. | Delta-P is +5% over clean, inside the normal band, but outlet temperature sag is the earlier duty-loss signal. | WO-8810; TT-1063O; FT-1063 | 2026-09-30 |
| P2 | TK-1121 (T-118) | Calibrate LT-1121 against the gauging tape at the next external inspection and record the deviation. | Level is the safety-critical measurement on the tank and the register interval is the standing control. | WO-8802; LT-1121 | 2026-12-15 |
| P2 | C-1071 (C-3) | Reduce load and notify the shift supervisor immediately if vibration reaches 7.1 mm/s or bearing temperature reaches 85 degC. | These are the alarm limits fixed by the machine manual and SOP-07.3 rev4. | SOP-07.3 rev4 s.4; C-3 manual Table 7-2 | 2026-09-30 |
| P2 | ESD-1182 | Run the emergency shutdown proof test and confirm the final element stroke time against the safety requirement. | A safety element that has not been proof-tested is an unverified layer. | SOP-41.2 rev8; ESD-1181 | 2026-11-05 |
| P2 | V-1047 (V-2210) | Overhaul the actuator and re-profile the position loop if the position feedback mismatch recurs. | The overlay vessel's live issue sits on a valve with actuator position feedback; a recurring mismatch is an actuator fault signature. | SOP-52.4 rev2; ZT-1047 | 2026-11-20 |
| P3 | C-1071 (C-3) | Review the learned vibration baseline after the bearing intervention and re-establish it only after a stable 30-day run. | Re-baselining before the machine stabilises hides the next deviation. | IR-204; vibration baseline record | 2026-11-30 |
| P3 | P-1042 | Add a discharge-pressure trend alarm at 17.0 bar in the console if one is not already configured. | The learned rule pins the alert threshold at 17 bar; it should be enforced by the control system, not by operator attention. | Learned rule: P-1042 17 bar | 2026-10-31 |
| P3 | C-1071 (C-3) | Align the learned rule "C-3 vibration baseline: 5.7 mm/s at 8,800 rpm" with the register twin's RPM-1071 nominal of 8,840 rpm. | The 40 rpm difference is a documentation artefact and should not propagate into a trip calculation. | Learned rule; RPM-1071 | 2026-11-15 |
| P3 | E-1063 | Schedule the bundle eddy-current survey at the next 48-month interval rather than at the next opportunity. | Fouling is the only credible degradation path and the bundle sample showed no wall loss; the interval can be held. | IR record (E-1063); fouling trend | 2027-03-01 |
| P3 | TK-1121 (T-118) | Inspect the roof seal and secondary containment at the next six-monthly external inspection. | Static containment degradation is slow and invisible between inspections. | WO-8802; tank inspection cycle | 2026-12-15 |
| P3 | C-1071 (C-3) | Update the C-3 asset record in the console overlay after the bearing intervention so the overlay and register narratives stay in step. | The overlay record still shows the pre-intervention values; a stale overlay record is how the next investigation starts from the wrong baseline. | Section 4b; IR-198; ME-198 | 2026-10-20 |
| P3 | P-1042 | Record the operating limit and the transmitter envelope side by side on the loop documentation. | The two numbers differ by design and the distinction caused confusion during the current investigation. | PT-1042A envelope; learned rule 17 bar | 2026-10-31 |
| P3 | ESD-1181 | Verify detector coverage and recalibrate the channel sitting at the 2% drift limit. | One detector reached the drift limit at the last proof test. | SOP-41.2 rev8; proof-test record | 2026-11-05 |
| P3 | M-1143 | Repeat the winding insulation-resistance test and current-signature check on the BFD fan motor. | The motor is one of the oldest registered drives and overload is a modelled failure mode for it. | SOP-18.3 rev4; sc-motor-overload | 2026-11-25 |
| P3 | C-1082 | Confirm the FCC air blower surge margin and test the trip path. | A blower trip starves reactor air; the trip path must be proven rather than assumed. | sc-compressor-trip; SOP-18.3 rev4 | 2026-12-10 |
| P3 | COL-1044 | Verify column pressure against the redundant transmitter and confirm the relief path to flare. | The atmospheric column is the pressure-surge scenario target and the relief path is the mitigation. | sc-pressure-surge; SOP-27.9 rev3 | 2026-11-28 |
| P3 | F-1043 | Survey tube skin temperatures and confirm excess oxygen at the crude charge heater. | Fired heaters degrade silently through tube temperature; the survey is the first-line check. | SOP-09.6 rev5 | 2026-12-05 |
| P3 | E-1045 | Trend the overhead condenser outlet temperature against duty to catch the instrument-drift scenario early. | The overhead condenser is the target of both the drift and fouling scenarios. | sc-temp-anomaly; sc-exchanger-fouling | 2026-12-12 |
| P3 | P-1131 | Confirm cooling-water pump duty against the tower cell performance. | Cooling capacity sets the achievable rate across the whole plant; a slow loss of duty is easy to miss. | UT-1133; cooling area record | 2027-01-15 |
| P3 | F-1141 | Check boiler feedwater quality and boiler efficiency against the commissioned curve. | Steam supply is a plant-wide dependency and efficiency drift is cumulative. | P-1142; steam area record | 2027-01-20 |
| P3 | C-1152 | Service the plant air compressor and verify instrument-air dew point. | Instrument air quality directly affects every pneumatic actuator and positioner. | UT-1151; utilities record | 2027-01-30 |
| P3 | VS-1162 | Inspect the flare knock-out drum internals and confirm the liquid seal. | The flare path is the last line of defence for every relief scenario in the plant. | UT-1161; flare area record | 2027-02-10 |
| P3 | P-1171 | Verify API separator oil removal and lift-pump duty. | Wastewater carry-over is an environmental exposure and an early indicator of upsets elsewhere. | VS-1172; wastewater record | 2027-02-28 |

### 22.1 Priority counts

| Priority | Actions |
|---|---|
| P1 | 6 |
| P2 | 8 |
| P3 | 18 |

### 22.2 Immediate sequence

The first four actions are ordered: (1) sustain once-per-shift monitoring on C-1071; (2) close the APR-231 approval decision so WO-8852 can be scheduled; (3) confirm suction conditions on P-1042 before any mechanical work; (4) confirm the V-1047/V-2210 level loop holds after the drain. Everything else can follow the normal planning cycle.

### 22.3 Verification and close-out

Each action closes only against a measurable acceptance criterion. The criteria below are the ones an auditor should ask for; a work order that is closed without them is closed on activity, not on outcome.

| Action family | Acceptance criterion | Evidence to file |
|---|---|---|
| C-3 bearing inspection | Overall vibration inside 10% of the re-established baseline with stable 2x, bearing temperature within 5 degC of baseline | IR-204; new inspection report; new baseline record |
| C-3 monitoring | Once-per-shift readings logged with no reading above 7.1 mm/s or 85 degC | Shift log; console trend export |
| C-3 approval | APR-231 decided and the decision recorded against WO-8852 | Approval record; work-order history |
| P-1042 suction check | Suction pressure and upstream level inside normal bands at the observed discharge pressure | Trend plot of FT-1042 against PT-1042A/B |
| P-1042 mechanical | Discharge pressure back inside the 17.0 bar operating limit at the same flow | Post-work survey; impeller inspection record |
| V-2210 level | Level loop holds inside the normal band and no detector latched in the area | WO-8837 close-out; detector reset record |
| Exchanger fouling | Delta-P trend and outlet temperature at constant flow tracked quarterly | WO-8810 review note |
| Tank inspection | Level transmitter within 0.5% of the gauging tape; containment dry | WO-8802 report; calibration sheet |
| Safety proof tests | Final element stroke time inside the safety requirement; detector drift inside 2% | Proof-test certificate |
| Rotating surveys | Vibration and current inside the normal band after intervention | Condition-monitoring report |
