# Project 117 — backend image
#
# Build context MUST be the repo root so pyproject.toml, uv.lock, and the
# vendor/localGPT directory are available.
#
#   docker buildx build -f infrastructure/docker/backend.Dockerfile \
#                        -t project117-backend .
#
# The vendor/localGPT directory is added to PYTHONPATH rather than installed
# via pip — it ships as a checked-in vendor tree that is imported at runtime.
# Expect a ~2–3 GB image (FastAPI + SQLAlchemy + LanceDB + sentence-transformers).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Add vendored localGPT to Python's module search path so
#   from rag_system.xxx import ...
# works inside the container without a pip-editable install.
ENV PYTHONPATH=/srv/vendor

# Install uv for fast, reproducible, lock-file-faithful installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# Copy dependency manifests first (maximises Docker layer cache reuse).
# pyproject.toml and uv.lock live at repo root, not backend/.
COPY pyproject.toml uv.lock ./

# Install all production dependencies declared in pyproject.toml.
# --no-dev excludes test / lint extras from the image.
RUN uv sync --frozen --no-dev

# Copy backend application source
COPY backend/ ./backend/

# Copy vendored libraries used at runtime (localGPT BM25/LanceDB retriever)
COPY vendor/ ./vendor/

EXPOSE 8000

# The real application factory lives in backend/api/src/main.py.
CMD ["uv", "run", "uvicorn", "backend.api.src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]