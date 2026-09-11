---
doc_id: refinery-technical-knowledge-base
chunk: 21
section: Lessons Learned
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, lessons]
---
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
