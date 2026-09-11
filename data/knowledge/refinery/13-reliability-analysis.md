---
doc_id: refinery-technical-knowledge-base
chunk: 13
section: Reliability Analysis
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, reliability]
---
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
