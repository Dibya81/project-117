---
doc_id: refinery-technical-knowledge-base
chunk: 3
section: Refinery Units
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, units]
---
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
