---
doc_id: refinery-technical-knowledge-base
chunk: 22
section: Recommended Actions
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, actions]
---
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
