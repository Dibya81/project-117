"""Trend projection and equipment assessment.

:mod:`simulator` fits and projects one signal; :mod:`digital_twin` assembles
several signals into an assessment of one asset. Both are statistical over
recorded measurements - neither models process physics, and both say so in
their output.
"""

from __future__ import annotations

from backend.tools.simulation.digital_twin import (
    WARNING_FRACTION,
    assess,
    assess_signal,
    compare_to_baseline,
    health_index,
)
from backend.tools.simulation.simulator import (
    GOOD_FIT_R2,
    MIN_POINTS,
    Fit,
    Sample,
    describe_trend,
    linear_fit,
    parse_series,
    project,
    time_to_threshold,
)

__all__ = [
    "GOOD_FIT_R2",
    "MIN_POINTS",
    "WARNING_FRACTION",
    "Fit",
    "Sample",
    "assess",
    "assess_signal",
    "compare_to_baseline",
    "describe_trend",
    "health_index",
    "linear_fit",
    "parse_series",
    "project",
    "time_to_threshold",
]
