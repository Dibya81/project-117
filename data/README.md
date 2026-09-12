# data/

Runtime + dataset data.

- `corpus/` — the real document corpus (PDF/DOCX/PPTX/XLSX); ingested into
  LanceDB by `scripts/ingest_corpus.py`
- `lancedb/` — the ingested retrieval index (git-ignored, created at runtime)
- `fixtures/` — test fixtures

Uploaded documents are stored in `data/uploads/` (git-ignored, created at runtime).
The simulation plant definitions live in `data/simulation.db` (git-ignored, seeded
from `project-117-simulation/database/seed_plants.sql`). Runtime work orders and
approval decisions live in `data/operations.db` (git-ignored).