"""
ENGAGEMENT + ENGAGEMENT RATE EVALUATION (spec sections 11/12).

Calls the REAL backend/app/analytics/engine.py functions on controlled,
synthetic rows built specifically to exercise: normal values, all-zero
values, and each individually-missing metric. The expected value for each
case is computed independently right here (plain Python), then compared to
what the production function actually returns.

Rule under test, taken from engine.py's own docstring: engagement =
reactions_total (falling back to `likes` only when reactions_total itself
is missing) + comments_count + shares -- summing only the components that
are actually present per row, and returning None (never a fabricated 0)
when nothing is present at all.
"""

from __future__ import annotations

import math

import pandas as pd

from evaluation.metrics.stats import independent_mean, independent_median, independent_percentile, within_tolerance
from evaluation.utils.backend_bridge import load_production_modules

# Each case: (row_dict, expected_engagement). None means "expect None" --
# i.e. this must never come back as 0 or NaN.
CASES: list[tuple[dict, float | None]] = [
    ({"reactions_total": 10000, "likes": 10000, "comments_count": 500, "shares": 100}, 10600),
    ({"reactions_total": None, "likes": 10000, "comments_count": 500, "shares": 100}, 10600),
    ({"reactions_total": 0, "likes": 0, "comments_count": 0, "shares": 0}, 0),
    ({"reactions_total": None, "likes": None, "comments_count": None, "shares": None}, None),
    ({"reactions_total": 5000, "likes": 5000, "comments_count": None, "shares": None}, 5000),
    ({"reactions_total": None, "likes": None, "comments_count": 42, "shares": None}, 42),
    ({"reactions_total": 100, "likes": 100, "comments_count": 10, "shares": None}, 110),
]

RATE_CASES: list[tuple[float | None, int | None, float | None]] = [
    # (avg_engagement, followers, expected_rate_pct)
    (10000, 1000000, 1.0),
    (10000, None, None),
    (10000, 0, None),
    (0, 1000000, 0.0),
    (None, 1000000, None),
]


def evaluate_engagement_formula() -> dict:
    mods = load_production_modules()
    eng = mods["analytics_engine"]
    results = []
    all_pass = True
    for row, expected in CASES:
        df = pd.DataFrame([row])
        actual_series = eng.compute_engagement_series(df)
        actual = actual_series.iloc[0]
        actual = None if (actual is None or (isinstance(actual, float) and math.isnan(actual))) else actual
        ok = within_tolerance(expected, actual)
        all_pass = all_pass and ok
        results.append({"input": row, "expected": expected, "actual": actual, "status": "PASS" if ok else "FAIL"})
    return {"cases_tested": len(CASES), "all_passed": all_pass, "cases": results}


def evaluate_engagement_rate_formula() -> dict:
    mods = load_production_modules()
    eng = mods["analytics_engine"]
    results = []
    all_pass = True
    for avg_engagement, followers, expected in RATE_CASES:
        # calculate_engagement_rate derives avg engagement from a DataFrame
        # itself, so build a single-row df whose engagement resolves to
        # exactly avg_engagement via reactions_total.
        df = pd.DataFrame([{"reactions_total": avg_engagement, "comments_count": 0, "shares": 0}]) \
            if avg_engagement is not None else pd.DataFrame([{"reactions_total": None, "comments_count": None, "shares": None}])
        actual = eng.calculate_engagement_rate(df, followers)
        # Guard against Infinity/NaN escaping the production function --
        # spec section 12 explicitly forbids these appearing at all.
        invalid = isinstance(actual, float) and (math.isinf(actual) or math.isnan(actual))
        ok = (not invalid) and within_tolerance(expected, actual, abs_tol=0.01)
        all_pass = all_pass and ok
        results.append({
            "avg_engagement": avg_engagement, "followers": followers,
            "expected_pct": expected, "actual_pct": actual,
            "status": "FAIL (Infinity/NaN escaped)" if invalid else ("PASS" if ok else "FAIL"),
        })
    return {"cases_tested": len(RATE_CASES), "all_passed": all_pass, "cases": results}


# ---------------------------------------------------------------------------
# Average / median / P90 (spec section 13) -- folded in here rather than a
# separate file, matching the evaluators/ layout the master prompt itself
# settles on in its final project-structure section.
# ---------------------------------------------------------------------------

# A controlled dataset with an unambiguous, hand-checkable mean/median/P90.
_CONTROLLED_VALUES = [10, 20, 30, 40, 50]


def evaluate_average_median() -> dict:
    mods = load_production_modules()
    eng = mods["analytics_engine"]
    # likes/comments_count checked on their own (reactions_total/shares left
    # unset so they can't leak into calculate_average_likes/_comments, which
    # only ever read their own column anyway). Engagement/P90 checked on a
    # SEPARATE frame where reactions_total alone carries the value -- mixing
    # the two into one frame would make engagement = reactions_total +
    # comments_count = 2x the controlled value, not the value itself.
    values_df = pd.DataFrame([{"likes": v, "comments_count": v} for v in _CONTROLLED_VALUES])
    engagement_df = pd.DataFrame([{"reactions_total": v, "comments_count": 0, "shares": 0}
                                   for v in _CONTROLLED_VALUES])

    checks = [
        ("average_likes", independent_mean(_CONTROLLED_VALUES), eng.calculate_average_likes(values_df)),
        ("median_likes", independent_median(_CONTROLLED_VALUES), eng.calculate_median_likes(values_df)),
        ("average_comments", independent_mean(_CONTROLLED_VALUES), eng.calculate_average_comments(values_df)),
        ("median_comments", independent_median(_CONTROLLED_VALUES), eng.calculate_median_comments(values_df)),
        ("average_engagement", independent_mean(_CONTROLLED_VALUES), eng.calculate_average_engagement(engagement_df)),
        ("median_engagement", independent_median(_CONTROLLED_VALUES), eng.calculate_median_engagement(engagement_df)),
        ("p90_engagement", independent_percentile(_CONTROLLED_VALUES, 0.90), eng.calculate_p90_engagement(engagement_df)),
    ]
    results = []
    all_pass = True
    for name, expected, actual in checks:
        ok = within_tolerance(expected, actual, abs_tol=0.5)
        all_pass = all_pass and ok
        results.append({"metric": name, "expected": expected, "actual": actual,
                         "status": "PASS" if ok else "FAIL"})
    return {"dataset": _CONTROLLED_VALUES, "all_passed": all_pass, "cases": results}
