#!/usr/bin/env bash
# Phase 0.5 cleanup: remove dead code and the ToolOrchestra working tree.
#
# These are deletions, so they are deliberately NOT bundled into the patch -
# a diff that removes 97 MB is unreviewable. Read the decision records first:
#   docs/decisions/0002-remove-toolorchestra.md
#   docs/decisions/0003-phase-0.5-hardening.md
#
# Run from anywhere; the script locates the repository root itself.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "repository root: $(pwd)"
echo

# --- 1. dead module ------------------------------------------------------
# backend/backend/graph/ has no __init__.py, so __init__data.py was never
# importable by anything. The typed graph errors it declares are reintroduced
# by Phase 5, in a real package, when graph memory actually lands.
dead="backend/backend/graph/__init__data.py"
if [ -f "${dead}" ]; then
  rm -f "${dead}"
  rmdir "backend/backend/graph" 2>/dev/null || true
  echo "removed ${dead}"
else
  echo "skip: ${dead} is already gone"
fi

# --- 2. ToolOrchestra ----------------------------------------------------
# 97 MB RL training harness, zero runtime value. The idea we keep is its
# tool-metadata schema (cost / latency / capability / permissions / risk),
# which Phase 8 implements in our own registry.
if [ -d "ToolOrchestra-main" ]; then
  echo "ToolOrchestra-main size: $(du -sh ToolOrchestra-main | cut -f1)"
  rm -rf ToolOrchestra-main
  echo "removed ToolOrchestra-main/"
else
  echo "skip: ToolOrchestra-main/ is already gone"
fi

# --- 3. stale database ---------------------------------------------------
# init_db uses create_all, which never ALTERs an existing table, so the new
# audit_events columns are missing from any database created before Phase 0.5.
# Queries would fail with "no such column". Alembic arrives in Phase 17.
if [ -f "data/project117.db" ]; then
  echo
  echo "NOTE: data/project117.db predates the Phase 0.5 audit_events columns."
  echo "      Delete it (development data only) before running the API:"
  echo "        rm data/project117.db"
fi

echo
echo "Done. Now verify - Phase 0.5 is not complete until all four pass:"
echo "  cd backend"
echo "  uv sync"
echo "  uv run pytest -q"
echo "  uv run ruff check backend tests"
echo "  uv run pyright backend"
