---
doc_id: refinery-technical-knowledge-base
chunk: 2
section: Plant Overview
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, plant]
---
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
