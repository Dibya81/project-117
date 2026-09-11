---
doc_id: refinery-technical-knowledge-base
chunk: 7
section: Maintenance History
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, maintenance]
---
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
