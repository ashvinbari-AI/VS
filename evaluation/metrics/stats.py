"""
Independent arithmetic for the metric-validation evaluators (spec section
13) -- deliberately reimplemented with stdlib `statistics`/plain Python
rather than importing backend/app/analytics/engine.py's own helpers, so
that comparing "expected" vs "production" is actually comparing two
independent implementations, not the same code against itself.
"""

from __future__ import annotations

import statistics
from typing import Sequence


def independent_mean(values: Sequence[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.fmean(vals), 4) if vals else None


def independent_median(values: Sequence[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.median(vals), 4) if vals else None


def independent_percentile(values: Sequence[float | None], q: float) -> float | None:
    """q in [0, 1]. Uses the same linear-interpolation convention as
    pandas.Series.quantile (what the production code actually calls), so
    this checks the arithmetic, not a different percentile definition."""
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return round(vals[0], 4)
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return round(vals[lo] + (vals[hi] - vals[lo]) * frac, 4)


def percentage_difference(a: float | None, b: float | None) -> float | None:
    """(a - b) / b * 100 -- None (never Infinity/NaN) if either value is
    unavailable or b is zero."""
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / b * 100, 2)


def within_tolerance(expected: float | None, actual: float | None, abs_tol: float = 0.01) -> bool:
    """True if both are None (agreement on "unavailable"), or both are
    numbers within abs_tol of each other. False for a None/number
    mismatch -- that's a real disagreement, not a rounding wobble."""
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    return abs(float(expected) - float(actual)) <= abs_tol
