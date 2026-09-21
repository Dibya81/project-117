"""Compatibility shim — backend.main (M-3).

The application factory moved to ``backend.api.src.main`` when the project
layout was restructured. This module re-exports it under the old name so that
external scripts, deployment aliases, or documentation written before the move
continue to work.

Use ``backend.api.src.main:create_app`` in all new code and configuration.
"""

from backend.api.src.main import create_app as create_app  # noqa: F401

__all__ = ["create_app"]
