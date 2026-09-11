---
doc_id: refinery-technical-knowledge-base
chunk: 10
section: Safety Procedures
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, safety]
---
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
