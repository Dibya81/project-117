# IR-204 — Recycle Gas Compressor C-3, Vibration Inspection

**Equipment:** C-3 Recycle Gas Compressor (Elliott 29M9-6), Hydrotreater U-200
**Date of survey:** 2026-09-06
**Surveyed by:** Reliability Engineering
**Instrument:** portable analyser, tri-axial accelerometer, DE and NDE bearing housings

## 1. Summary of findings

Overall vibration on the drive-end (DE) bearing housing measured **6.8 mm/s RMS**,
against a 90-day rolling baseline of **5.8 mm/s** — an increase of **18%**. The
alarm limit for this machine is 7.1 mm/s (see manual excerpt, alarm limits table).
The increase has developed progressively over eight days, not as a step change.

## 2. Spectral observations

| Frequency | Amplitude | Interpretation |
|---|---|---|
| 1x running speed (49.6 Hz) | 4.9 mm/s | dominant; rising |
| 2x running speed | 1.1 mm/s | stable |
| Bearing defect band (BPFO) | 0.6 mm/s | slightly elevated |

Energy is concentrated at 1x running speed with a stable 2x component. Combined
with the DE bearing temperature rising from 68 degC to 79 degC over the same
window, this pattern is consistent with **progressive DE bearing wear or a
developing alignment shift**, not with looseness or blade-pass excitation.

## 3. Immediate recommendations

1. Increase vibration monitoring on C-3 to daily until amplitude stabilises
   (SOP-07.3 rev4, section 4.2).
2. Raise a corrective work order for DE bearing inspection at the next
   available window; do not exceed 14 days at the present trend.
3. Perform a hot alignment check before re-baselining (ME-198 procedure).
4. Confirm lube-oil condition and DE bearing oil supply temperature.

## 4. Related history

The DE bearing was last replaced in March 2025 (IR-198). An alignment check in
November 2025 (ME-198) recorded a coupling offset of 0.06 mm, within tolerance.
