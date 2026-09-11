---
doc_id: refinery-technical-knowledge-base
chunk: 5
section: Instrumentation
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, instrumentation]
---
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
