---
doc_id: refinery-technical-knowledge-base
chunk: 4
section: Equipment Register
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, equipment]
---
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
