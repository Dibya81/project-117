#!/usr/bin/env python3
"""Seed the on-prem knowledge corpus used by the Documentation agent.

These are synthetic-but-realistic operating documents for the two synthetic
plants that ship with Project 117 (Meridian Refinery, Kalinga Steelworks).
They exist so retrieval has a real corpus to search offline: each document is
scoped to a specific equipment kind and failure mechanism, which is what makes
different incidents retrieve different evidence instead of one universal SOP.

Run:  python3 scripts/seed_knowledge_corpus.py
Idempotent — rewrites the same files.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path("data/knowledge")

DOCS: dict[str, dict[str, str]] = {
    "SOP-14.2_instrument_failure": {
        "id": "SOP-14.2",
        "title": "Field Instrument Failure and Isolation",
        "kind": "instrument",
        "mechanism": "sensor_failure",
        "revision": "rev6",
        "body": """
## Scope

Applies to any field transmitter reporting BAD quality, a frozen value, or a
reading outside the configured critical envelope, on pressure, temperature,
flow or level service.

## Immediate actions

1. Mark the transmitter unavailable in the control system so the control loop
   stops using it as a process variable. Do not leave a failed transmitter in
   automatic cascade.
2. Identify a validated alternate measurement on the same equipment or the
   nearest upstream/downstream asset carrying the same medium.
3. Cross-check the alternate against a correlated measurement (flow against
   pump discharge pressure, temperature against duty) before trusting it.
4. If no consistent alternate exists, treat the process point as unreadable
   and move the unit to attended operation.

## Isolation and replacement

Isolate at the root valve, depressurise the impulse line, and lock out before
removing the transmitter. A replacement must be bench-verified at zero and
span before reinstatement. Record the serial number against the asset tag.

## Verification before returning to automatic

The new or repaired instrument must track the validated alternate within 2%
of span for ten consecutive scans, with no active critical alarm on the
affected equipment, before the loop is returned to automatic control.
""",
    },
    "SOP-14.7_instrument_drift": {
        "id": "SOP-14.7",
        "title": "Instrument Drift and Calibration Recovery",
        "kind": "instrument",
        "mechanism": "instrument_drift",
        "revision": "rev3",
        "body": """
## Scope

Governs transmitters whose reading walks away from correlated measurements
without a corresponding process change — calibration drift rather than an
abrupt instrument failure.

## Detection criteria

Drift is confirmed when the suspect measurement diverges progressively from a
redundant or correlated point while flow, duty and downstream conditions stay
stable. A single-scan excursion is not drift; a monotonic trend over several
minutes is.

## Response

1. Freeze any automatic control action that depends solely on the drifting
   point and transfer control to the validated alternate.
2. Raise a calibration work order against the asset tag, including the
   observed divergence and the reference measurement used.
3. Recalibrate at zero, mid and span. If drift recurs within one month,
   replace the sensing element rather than recalibrating again.

## Verification

After calibration, the instrument must agree with the reference measurement
within 2% of span across the normal operating range, held for ten consecutive
scans.
""",
    },
    "SOP-22.1_pump_bearing": {
        "id": "SOP-22.1",
        "title": "Centrifugal Pump Bearing Overheat and Vibration",
        "kind": "pump",
        "mechanism": "bearing_overheat",
        "revision": "rev5",
        "body": """
## Scope

Centrifugal pumps and their drivers showing rising bearing temperature,
rising vibration, or both, on any process service.

## Assessment

Compare bearing temperature against the vibration trend. Temperature rising
with vibration indicates mechanical degradation of the bearing. Temperature
rising alone, with stable vibration, more often indicates lubrication loss or
a cooling problem on the bearing housing.

## Immediate actions

1. Reduce load on the affected pump and confirm the spare or parallel path can
   carry the duty before any shutdown.
2. Check lubrication level and cooling water flow to the bearing housing.
3. If vibration exceeds the critical envelope, stop the pump on a controlled
   ramp. Do not trip a running pump on a critical service without confirming
   downstream inventory.

## Maintenance action

Bearing replacement requires the coupling to be disconnected and alignment
re-checked after reassembly. Record hours run since last inspection.

## Verification

After restoration: vibration and bearing temperature inside the normal
envelope, discharge pressure and flow restored to pre-fault values, and no
active critical alarm on the pump or its downstream assets.
""",
    },
    "SOP-22.4_pump_cavitation": {
        "id": "SOP-22.4",
        "title": "Pump Cavitation and Suction Starvation",
        "kind": "pump",
        "mechanism": "cavitation",
        "revision": "rev2",
        "body": """
## Scope

Pumps exhibiting erratic discharge pressure, falling flow, and elevated
vibration consistent with vapour formation at the impeller eye.

## Cause assessment

Cavitation follows insufficient net positive suction head: a closing or
partially blocked suction valve, a falling upstream level, a rising suction
temperature, or a strainer fouling. Check upstream level and suction pressure
before touching the pump itself.

## Immediate actions

1. Reduce pump speed or throttle discharge to lower demand on the suction.
2. Restore upstream inventory or open the suction path fully.
3. If suction conditions cannot be restored promptly, stop the pump. Sustained
   cavitation destroys the impeller and the mechanical seal.

## Verification

Discharge pressure steady within the normal envelope, vibration back to
baseline, upstream level recovering, and flow stable for ten consecutive
scans.
""",
    },
    "SOP-31.5_seal_leak": {
        "id": "SOP-31.5",
        "title": "Mechanical Seal Leak and Hydrocarbon Release",
        "kind": "pump",
        "mechanism": "seal_leak",
        "revision": "rev7",
        "body": """
## Scope

Any confirmed process leak from a mechanical seal, flange or pipe section,
including releases detected only by an area gas or leak detector.

## Immediate actions

1. Treat a tripped gas or leak detector as a real release until proven
   otherwise. Do not silence or bypass the detector.
2. Isolate the leaking section at the nearest upstream and downstream block
   valves and depressurise to the flare or drain system as applicable.
3. Establish an exclusion zone appropriate to the medium and check for ignition
   sources in the affected process area.
4. Notify the shift supervisor before any repair begins.

## Repair

Seal replacement requires the pump to be isolated, drained, purged and locked
out. Verify the seal flush plan is restored before returning to service.

## Verification

The area detector must return to and hold zero after the repair — a latched
detector left in the tripped state means the release has not been cleared and
the incident stays open. Confirm no active critical alarm on the repaired
asset or its neighbours before closing the work order.
""",
    },
    "SOP-18.3_rotating_trip": {
        "id": "SOP-18.3",
        "title": "Motor and Drive Trip / Electrical Overload",
        "kind": "motor",
        "mechanism": "overload",
        "revision": "rev4",
        "body": """
## Scope

Motors, drives and driven machines that trip on overload, or that draw current
above the rated envelope while running.

## Assessment

Rising current with rising vibration points to a mechanical load problem
(bearing, coupling, blocked path). Rising current with stable vibration points
to an electrical fault or a supply imbalance. Check the driven equipment's
discharge conditions before assuming a motor fault.

## Immediate actions

1. Do not reset and restart a tripped drive without establishing why it
   tripped. A second trip on the same fault damages the winding.
2. Confirm the downstream process can tolerate the loss of the machine, and
   start the spare where one exists.
3. Inspect the coupling and the driven shaft for locked rotation before any
   restart attempt.

## Verification

Motor current and vibration inside the normal envelope after restart, driven
equipment capacity restored, and no critical alarm on the affected process
area.
""",
    },
    "SOP-27.9_pressure_surge": {
        "id": "SOP-27.9",
        "title": "Pressure Surge in Vessels, Columns and Headers",
        "kind": "vessel",
        "mechanism": "pressure_surge",
        "revision": "rev3",
        "body": """
## Scope

Pressure vessels, separators, columns and headers experiencing a rapid rise in
pressure toward or beyond the critical envelope.

## Immediate actions

1. Confirm the pressure reading against a second transmitter before acting on
   a single point — a surge and a failed transmitter look similar for one scan.
2. Reduce inlet flow and confirm the relief path to flare is available and not
   isolated.
3. Check downstream restriction: a closed control valve or blocked exchanger is
   the most common cause of a surge in a stable unit.

## Prohibited actions

Do not isolate a relief device to stop a surge. Do not raise the alarm limits
to silence the alarm.

## Verification

Pressure returned inside the normal envelope and stable for ten consecutive
scans, relief path confirmed available, downstream flow restored, and no
active critical alarm on the vessel or connected assets.
""",
    },
    "SOP-09.6_furnace_thermal": {
        "id": "SOP-09.6",
        "title": "Fired Heater and Furnace Thermal Excursion",
        "kind": "furnace",
        "mechanism": "degrade",
        "revision": "rev5",
        "body": """
## Scope

Fired heaters, furnaces and reheat furnaces with tube or outlet temperatures
approaching the critical envelope, or with loss of a temperature measurement
on a fired pass.

## Immediate actions

1. Reduce firing rate before adjusting pass flows. Never increase firing to
   compensate for an unexplained temperature reading.
2. On loss of a pass temperature measurement, move the heater to attended
   operation and use skin thermocouples and outlet temperature as the control
   reference.
3. Maintain minimum pass flow at all times. Loss of flow with firing sustained
   causes tube damage within minutes.

## Verification

Outlet and pass temperatures inside the normal envelope, firing stable, fuel
flow within its band, and no critical alarm on the heater or downstream
fractionation.
""",
    },
    "SOP-41.2_gas_detection": {
        "id": "SOP-41.2",
        "title": "Area Gas and Leak Detection Response",
        "kind": "safety",
        "mechanism": "leak",
        "revision": "rev8",
        "body": """
## Scope

Fixed gas detectors and liquid leak detectors in all process areas.

## Detector behaviour

These are latched point devices: healthy state is zero, and a trip latches at
full scale until the release is cleared and the device is reset. A detector
reading zero is a healthy detector, not a failed one, and must not be treated
as an envelope violation.

## Response to a trip

1. Treat as a real release. Establish the exclusion zone for the process area
   reported by the detector.
2. Identify the source by correlating with pressure and flow changes on assets
   in the same area.
3. Isolate, depressurise and repair per the applicable equipment procedure.

## Reset and verification

Reset only after the release is confirmed cleared. The detector must read and
hold zero. An incident may not be closed while any detector in the affected
area remains latched.
""",
    },
    "SOP-52.4_valve_control": {
        "id": "SOP-52.4",
        "title": "Control Valve Sticking and Position Feedback Loss",
        "kind": "valve",
        "mechanism": "stick",
        "revision": "rev2",
        "body": """
## Scope

Control valves that fail to track their setpoint, and valves whose position
transmitter disagrees with the commanded position.

## Assessment

Compare commanded position, position feedback, and the process response. If
the process responds but feedback is frozen, the fault is in the position
transmitter. If neither responds, the valve or its actuator is stuck.

## Immediate actions

1. Place the loop in manual and hold the last known safe position.
2. Establish whether the process can be controlled from an alternate valve or
   by adjusting upstream duty.
3. Do not stroke a stuck valve repeatedly against a live process; isolate first
   where the service permits.

## Verification

Position feedback tracking the commanded position within 2%, process variable
back under control, and no critical alarm on connected equipment.
""",
    },
    "OPS-05.1_steelmaking_continuity": {
        "id": "OPS-05.1",
        "title": "Ironmaking and Steelmaking Process Continuity",
        "kind": "furnace",
        "mechanism": "degrade",
        "revision": "rev3",
        "body": """
## Scope

Operational continuity decisions across raw material handling, sinter, coke,
blast furnace, hot blast, gas cleaning, BOF, ladle, casting, reheat and
rolling.

## Continuity rules

The blast furnace and hot blast system cannot be interrupted for instrument
maintenance. Degraded instrumentation on these units is managed by moving to
attended operation with a validated alternate measurement, not by stopping the
unit.

Casting and rolling can tolerate a short controlled stop; raw material and
sinter handling can be bypassed to stockpile for a limited period.

## Impact assessment

Before recommending continued operation, confirm: the affected asset's
downstream neighbours still have a flow path, no critical alarm is active in
the affected area, and a compensating measurement exists for every control
loop that lost its primary input.
""",
    },
    "OPS-03.2_refinery_continuity": {
        "id": "OPS-03.2",
        "title": "Refinery Unit Continuity and Compensating Monitoring",
        "kind": "column",
        "mechanism": "degrade",
        "revision": "rev4",
        "body": """
## Scope

Continuity decisions across crude receiving and storage, desalting, crude and
vacuum distillation, naphtha hydrotreating, reforming, catalytic cracking,
diesel hydrotreating, sulphur recovery, hydrogen, product storage and
utilities.

## Compensating monitoring

A unit may continue to run with a failed instrument only when a validated
alternate measurement covers the same control objective, the operator is
notified, and the condition is reviewed at the next shift handover.

Crude distillation and vacuum distillation may not run unattended with a lost
column temperature or level measurement.

## Escalation

Escalate to a controlled rate reduction when two or more measurements on the
same service are unavailable, when a detector is latched in the affected area,
or when the downstream unit loses its only flow path.
""",
    },
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in DOCS.items():
        front = (
            "---\n"
            f"id: {doc['id']}\n"
            f"title: {doc['title']}\n"
            f"kind: {doc['kind']}\n"
            f"mechanism: {doc['mechanism']}\n"
            f"revision: {doc['revision']}\n"
            "classification: internal\n"
            "source: synthetic-operating-document\n"
            "---\n"
        )
        body = f"# {doc['title']} ({doc['id']}, {doc['revision']})\n{doc['body'].rstrip()}\n"
        (OUT / f"{name}.md").write_text(front + body, encoding="utf-8")
    print(f"wrote {len(DOCS)} documents to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
