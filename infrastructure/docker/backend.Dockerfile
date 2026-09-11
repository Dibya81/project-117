# Project 117 — backend image (Phase 1+)
#
# Build context is the repo root so that LightRAG-main (editable dep) and
# localGPT-main (sys.path vendor) are available inside the image.
#
# docker buildx build -f infrastructure/docker/backend.Dockerfile -t project117-backend .
#
# Phase 1–4 note: torch/transformers are installed here as part of
# localGPT's dependency stack. Expect a ~4–6 GB image. If you only
# need Phase 1–2 (no ingestion/RAG), comment out the LightRAG/localGPT
# COPY lines and pin lancedb in pyproject.toml without torch.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# Copy dependency manifests first (layer cache friendly)
COPY backend/pyproject.toml backend/uv.lock backend/
COPY LightRAG-main/ LightRAG-main/

# Install backend + LightRAG editable dep (localGPT is sys.path vendor, not pip)
RUN uv sync --project backend --frozen --no-dev

# Copy source
COPY backend/backend /srv/backend/backend
COPY backend/README.md /srv/backend/README.md

# Copy vendored libraries used at runtime
COPY localGPT-main/ localGPT-main/

EXPOSE 8000

CMD ["uv", "run", "--project", "backend", "uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]