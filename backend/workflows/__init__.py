"""Deterministic workflows (Phase 15).

YAML definitions live in the repo-level ``workflows/`` directory. Phase 15
adds the loader + engine (steps, conditions, retries, timeouts, approval
gates, tool/agent execution, verification). Phase 1 ships an empty registry so
``GET /api/workflows`` is a real endpoint.
"""
