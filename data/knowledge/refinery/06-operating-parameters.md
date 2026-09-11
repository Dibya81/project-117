---
doc_id: refinery-technical-knowledge-base
chunk: 6
section: Operating Parameters
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, parameters]
---
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
