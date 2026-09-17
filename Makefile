# Project 117 — developer entry points.
#
# Every backend target runs from the REPOSITORY ROOT on purpose:
#   * pyproject.toml / uv.lock / tests/ live here, not in backend/;
#   * `backend.config` resolves `.env` from the current working directory;
#   * the package is imported as `backend.*`, which only resolves from here.
# The previous version `cd backend` for every target, which made `uv sync`
# (no pyproject there), `pytest` (no tests there) and the uvicorn factory
# (`backend.main`, a module that does not exist) all fail.

.PHONY: help install run web workbench test lint typecheck check test-web \
        typecheck-web health clean

PY := .venv/bin/python
# Bound to every interface on purpose. The Android app in apps/mobile runs on a
# device or emulator that cannot reach the host's loopback: a phone needs the
# machine's LAN address and an emulator needs 10.0.2.2. With --host 127.0.0.1
# the API answers curl on this machine and nothing else, which the app reports
# as "Backend offline" because the connection is refused before any HTTP status
# exists. Access is still gated: every /api/v1 route requires enrollment + login.
UVICORN := uvicorn backend.api.src.main:create_app --factory --host 0.0.0.0 --port 8000

help:
	@echo "install         Install backend (uv) and JS workspace (pnpm) dependencies"
	@echo "run             Backend API on http://127.0.0.1:8000"
	@echo "web             Console on http://127.0.0.1:3017   (apps/web, Next.js)"
	@echo "workbench       Simulation workbench on http://127.0.0.1:5173 (frontend/, Vite)"
	@echo "test            Backend test suite (pytest)"
	@echo "lint            Backend lint (ruff)"
	@echo "typecheck       Backend types (pyright) + console types (tsc)"
	@echo "check           lint + typecheck + test"
	@echo "health          Probe the running backend"
	@echo "clean           Remove caches and generated runtime data"

install:
	uv sync
	pnpm install

run:
	uv run $(UVICORN)

web:
	pnpm --filter web dev

workbench:
	pnpm --prefix frontend dev

test:
	uv run pytest -q

lint:
	uv run ruff check backend tests

typecheck:
	uv run pyright backend
	pnpm --filter web typecheck

test-web:
	pnpm --filter web typecheck

typecheck-web:
	pnpm --filter web typecheck

check: lint typecheck test

health:
	@curl -fsS http://127.0.0.1:8000/health | $(PY) -m json.tool

clean:
	rm -rf .pytest_cache .ruff_cache .pyright
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf apps/web/.next frontend/dist
	rm -rf data/uploads/* data/artifacts/*
