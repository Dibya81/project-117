# workflows/

Deterministic workflow definitions (YAML) will live here (Phase 15), e.g.:

- `mrpl/` — maintenance report pipelines
- `examples/` — `maintenance-investigation.yaml`, `inspection-analysis.yaml`,
  `report-generation.yaml`, `document-analysis.yaml`, `equipment-investigation.yaml`

The workflow engine in `backend/workflows/` will load these at runtime.