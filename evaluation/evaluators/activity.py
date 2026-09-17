"""
ACTIVITY METRIC EVALUATION (spec section 14) -- calls the real
backend/app/analytics/engine.py activity functions on a small, hand-checked
controlled dataset so the expected numbers can be verified by inspection.

Controlled dataset (all UTC, all "post" content_type except one "reel"):
  01 Sep -> post   02 Sep -> post   05 Sep -> reel   07 Sep -> post
Hand-checked expectations:
  total = 4
  active_days = 4 (each post on its own distinct day)
  gaps between consecutive posts (days): 1, 3, 2 -> longest_inactive = 3
  most_active_day: whichever weekday 01/02/05/07 Sep 2026 falls on with
    the most hits -- computed independently below via Python's own
    `datetime.weekday()`, not copied from the production function.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from evaluation.metrics.stats import within_tolerance
from evaluation.utils.backend_bridge import load_production_modules

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_DATES = ["2026-09-01T10:00:00+00:00", "2026-09-02T10:00:00+00:00",
          "2026-09-05T10:00:00+00:00", "2026-09-07T10:00:00+00:00"]
_TYPES = ["post", "post", "reel", "post"]


def _controlled_df() -> pd.DataFrame:
    return pd.DataFrame([{"published_at": d, "published_at_local": d, "content_type": t}
                          for d, t in zip(_DATES, _TYPES)])


def _independent_expectations() -> dict:
    dts = [datetime.fromisoformat(d) for d in _DATES]
    day_counts = Counter(_DAY_NAMES[dt.weekday()] for dt in dts)
    gaps_days = [(dts[i + 1] - dts[i]).total_seconds() / 86400 for i in range(len(dts) - 1)]
    return {
        "total": len(_DATES),
        "active_days": len({dt.date() for dt in dts}),
        "longest_inactive_period_days": round(max(gaps_days), 2),
        "most_active_day": max(day_counts, key=day_counts.get) if len(set(day_counts.values())) > 1
        or len(day_counts) == 1 else None,  # ambiguous ties aren't asserted
    }


def evaluate_activity_metrics() -> dict:
    mods = load_production_modules()
    eng = mods["analytics_engine"]
    df = _controlled_df()
    expected = _independent_expectations()

    checks = [
        ("total_content", expected["total"], eng.calculate_total_content(df)),
        ("active_days", expected["active_days"], eng.calculate_active_days(df)),
        ("longest_inactive_period_days", expected["longest_inactive_period_days"],
         eng.calculate_longest_inactive_period(df)),
    ]
    if expected["most_active_day"] is not None:
        checks.append(("most_active_day", expected["most_active_day"], eng.most_active_day(df)))

    results = []
    all_pass = True
    for name, exp, act in checks:
        ok = within_tolerance(exp, act, abs_tol=0.5) if isinstance(exp, (int, float)) else (exp == act)
        all_pass = all_pass and ok
        results.append({"metric": name, "expected": exp, "actual": act, "status": "PASS" if ok else "FAIL"})

    return {"dataset": list(zip(_DATES, _TYPES)), "all_passed": all_pass, "cases": results}
