# data/demo — deterministic demo dataset

One coherent story, identical on every run and every machine:

* **C-3 Recycle Gas Compressor** vibration has risen 18% above a 5.8 mm/s
  baseline to 6.8 mm/s, with 1x dominance and DE bearing temperature rising.
* **IR-204** (`inspection-reports/`) records the survey and its recommendations.
* **SOP-07.3 rev4** (`sop/`) defines the required response and the approval rule.
* **WO-8852** (`work-orders.json`) is the resulting corrective work order.
* **APR-231** (`approvals.json`) is the outage approval that gates it.
* `telemetry/telemetry.json` carries the 24-point trends behind those numbers.
* `history.json` carries the prior bearing replacement and alignment checks.

Every API response built from this dataset is labelled `source: "demo-dataset"`.
If this directory is absent, the operations endpoints answer HTTP 503
(`demo_data_unavailable`) rather than inventing records.

Regenerate with: `python scripts/seed_demo_data.py`
