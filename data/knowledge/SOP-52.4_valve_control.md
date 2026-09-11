---
id: SOP-52.4
title: Control Valve Sticking and Position Feedback Loss
kind: valve
mechanism: stick
revision: rev2
classification: internal
source: synthetic-operating-document
---
# Control Valve Sticking and Position Feedback Loss (SOP-52.4, rev2)

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
