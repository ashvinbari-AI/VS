"""
COMPARISON ENGINE EVALUATION (spec sections 24/25) -- calls the real
backend/app/analytics/comparison.py `calculate_comparison_metrics()` on
controlled Person A / Person B datasets with a hand-known correct answer,
plus the edge cases the spec calls out by name (A>B, B>A, A=B, missing,
zero, null). The comparison engine must never use an LLM for these
decisions -- this evaluator is checking that the *Python* winner logic
(higher/lower/equal) is right, nothing about narrative/sentiment.
"""

from __future__ import annotations

import math

import pandas as pd

from evaluation.utils.backend_bridge import load_production_modules


def _content_df(n: int, avg_likes: float | None, avg_comments: float | None) -> pd.DataFrame:
    if n == 0:
        return pd.DataFrame(columns=["likes", "comments_count", "reactions_total", "shares",
                                      "content_type", "published_at"])
    rows = []
    for i in range(n):
        rows.append({
            "likes": avg_likes, "comments_count": avg_comments,
            "reactions_total": avg_likes, "shares": 0, "content_type": "post",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T10:00:00+00:00",
        })
    return pd.DataFrame(rows)


_SCENARIOS = [
    # name, (n_a, likes_a, comments_a, followers_a), (n_b, likes_b, comments_b, followers_b), expected_winner_per_key
    ("person_a_more_content_person_b_more_comments",
     (10, 10000, 500, 1_000_000), (20, 8000, 700, 1_000_000),
     {"total_content": "person_b", "average_likes": "person_a", "average_comments": "person_b"}),
    ("equal_likes_no_winner",
     (5, 5000, 100, 500_000), (5, 5000, 200, 500_000),
     {"average_likes": None, "average_comments": "person_b"}),
    ("person_b_missing_content",
     (5, 5000, 100, 500_000), (0, None, None, None),
     {"total_content": "person_a", "average_likes": None}),  # b's avg_likes is None -> no winner, never fabricated
    ("both_zero_followers",
     (5, 5000, 100, 0), (5, 4000, 90, 0),
     {"engagement_rate": None}),  # followers=0 -> rate must be None, not divide-by-zero
]


def evaluate_comparison_scenarios() -> dict:
    mods = load_production_modules()
    comp = mods["comparison_engine"]
    empty_comments = pd.DataFrame(columns=["content_id"])

    results = []
    all_pass = True
    for name, a, b, expected_winners in _SCENARIOS:
        n_a, likes_a, comments_a, followers_a = a
        n_b, likes_b, comments_b, followers_b = b
        df_a = _content_df(n_a, likes_a, comments_a)
        df_b = _content_df(n_b, likes_b, comments_b)

        out = comp.calculate_comparison_metrics(
            "person_a", "person_b", df_a, df_b, empty_comments, empty_comments,
            followers_a, followers_b, period_days=30,
        )

        scenario_pass = True
        checks = []
        for key, expected_winner in expected_winners.items():
            actual_winner = out["comparisons"].get(key, {}).get("winner")
            actual_value = out["comparisons"].get(key, {})
            ok = actual_winner == expected_winner
            scenario_pass = scenario_pass and ok
            checks.append({"metric": key, "expected_winner": expected_winner,
                            "actual_winner": actual_winner, "person_a_value": actual_value.get("person_a"),
                            "person_b_value": actual_value.get("person_b"), "status": "PASS" if ok else "FAIL"})

        # Never allow Infinity/NaN to have escaped into any numeric comparison value.
        for key, c in out["comparisons"].items():
            for side in ("person_a", "person_b"):
                v = c.get(side)
                if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                    scenario_pass = False
                    checks.append({"metric": key, "status": "FAIL",
                                   "error": f"{side} produced Infinity/NaN"})

        all_pass = all_pass and scenario_pass
        results.append({"scenario": name, "all_passed": scenario_pass, "checks": checks})

    return {"scenarios_tested": len(_SCENARIOS), "all_passed": all_pass, "scenarios": results}
