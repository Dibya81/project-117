---
id: SOP-14.7
title: Instrument Drift and Calibration Recovery
kind: instrument
mechanism: instrument_drift
revision: rev3
classification: internal
source: synthetic-operating-document
---
# Instrument Drift and Calibration Recovery (SOP-14.7, rev3)

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
