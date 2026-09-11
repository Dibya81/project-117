---
id: SOP-14.2
title: Field Instrument Failure and Isolation
kind: instrument
mechanism: sensor_failure
revision: rev6
classification: internal
source: synthetic-operating-document
---
# Field Instrument Failure and Isolation (SOP-14.2, rev6)

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
