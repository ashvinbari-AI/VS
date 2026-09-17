"""
Evaluation CLI (spec sections 53-55).

    backend\\.venv\\Scripts\\python.exe -m evaluation.run [--module MODULE] [--save-baseline] [--out NAME]

Run from the project root (A:\\VS) using the BACKEND's own virtualenv --
that's where pandas/pyarrow/pydantic (and, for NLP, transformers/torch)
already live; this package adds no separate dependency set.

--module: all (default) | scraper | metrics | nlp | comparison
--save-baseline: also store this run's tracked metrics as the new
    regression baseline (never done automatically -- see evaluators/regression.py)
--out NAME: report file basename under evaluation/reports/ (default:
    a UTC timestamp)

Exit code: 0 if every scorecard entry is PASS/WARNING/NOT_EVALUATED, 1 if
any is FAIL (spec section 55 -- lets this hook into CI later).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from evaluation.config.thresholds import status_for
from evaluation.evaluators import (
    activity, comments as comment_theme_eval, comparison as comparison_eval,
    data_completeness, data_quality, duplicates, engagement, field_accuracy,
    issues, narrative, regression, sentiment,
)
from evaluation.utils import gt_adapter
from evaluation.utils.data_loader import load_nlp_cache, load_production_dataframes, rows_to_dicts
from evaluation.utils.io import load_ground_truth, write_csv_report, write_json_report

MODULES = ["scraper", "metrics", "nlp", "comparison"]


def _pct_from_cases(result: dict) -> float | None:
    cases = result.get("cases") or result.get("scenarios")
    if not cases:
        return 100.0 if result.get("all_passed") else (0.0 if "all_passed" in result else None)
    passed = sum(1 for c in cases if c.get("all_passed") or c.get("status") == "PASS")
    return round(passed / len(cases) * 100, 2)


def _combined_pct_from_cases(*results: dict) -> float | None:
    """Same idea as _pct_from_cases but pooled across several evaluator
    results (e.g. engagement formula + rate + average/median all count
    toward one "metric accuracy" scorecard entry, per spec section 27's
    single combined threshold for deterministic-metric arithmetic)."""
    total = passed = 0
    for result in results:
        if not result:
            continue
        cases = result.get("cases") or result.get("scenarios") or []
        total += len(cases)
        passed += sum(1 for c in cases if c.get("all_passed") or c.get("status") == "PASS")
    return round(passed / total * 100, 2) if total else None


def run_scraper_module(dfs, gt_posts, gt_comments, gt_pairs) -> dict:
    content_records = rows_to_dicts(dfs["content"])
    comments_records = rows_to_dicts(dfs["comments"])
    return {
        "completeness": {
            "content": data_completeness.evaluate_content_completeness(dfs["content"], gt_posts),
            "comments": data_completeness.evaluate_comments_completeness(dfs["comments"], gt_comments),
            "profiles": data_completeness.evaluate_profiles_completeness(dfs["profiles"]),
        },
        "field_accuracy": {
            "posts": field_accuracy.evaluate_post_fields(gt_posts, content_records),
            "comments": field_accuracy.evaluate_comment_fields(gt_comments, comments_records),
            "content_type": field_accuracy.evaluate_content_type_classification(gt_posts, content_records),
        },
        "data_quality": {
            "content": data_quality.evaluate_content_quality(dfs["content"]),
            "comments": data_quality.evaluate_comments_quality(dfs["comments"]),
        },
        "duplicates": duplicates.evaluate_duplicates(gt_pairs),
    }


def run_metrics_module() -> dict:
    return {
        "engagement": engagement.evaluate_engagement_formula(),
        "engagement_rate": engagement.evaluate_engagement_rate_formula(),
        "average_median": engagement.evaluate_average_median(),
        "activity": activity.evaluate_activity_metrics(),
    }


def run_nlp_module(nlp_cache: dict) -> dict:
    return {
        "sentiment": sentiment.evaluate_sentiment(gt_adapter.sentiment_ground_truth(), nlp_cache),
        "narrative": narrative.evaluate_narrative(gt_adapter.narrative_ground_truth(), nlp_cache),
        "comment_theme": comment_theme_eval.evaluate_comment_theme(gt_adapter.comment_theme_ground_truth(), nlp_cache),
        "issues": issues.evaluate_issues(gt_adapter.issues_ground_truth(), nlp_cache),
    }


def run_comparison_module() -> dict:
    return {"comparison": comparison_eval.evaluate_comparison_scenarios()}


LIMITATIONS = [
    "Ground-truth files under evaluation/ground_truth/ start empty; any module reporting "
    "NOT_EVALUATED simply has no manually verified data yet, not a passing or failing result.",
    "NLP evaluation reads whatever is already cached in data/analysis/nlp_cache.json -- it does "
    "not re-run Gemini or the local transformer model itself (spec section 57).",
    "Duplicate-detection evaluation checks production's actual rule (content_id equality) -- it "
    "cannot detect near-duplicate posts under two different ids; that is a real system limitation, "
    "not an evaluator gap.",
    "Geography evaluation is not implemented: the Geography feature was removed from this "
    "application, so there is nothing left to evaluate.",
]


def build_report(module: str = "all", run_id: str | None = None) -> dict:
    """Assembles a full (or single-module) evaluation report. The single
    source of truth both `main()` (the CLI) and backend/app/routers/
    evaluation.py (the dashboard API) call, so the two can never drift
    apart into reporting different numbers for the same run."""
    run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y_%m_%d_%H%M%S")

    dfs = load_production_dataframes()
    gt_posts = load_ground_truth("posts_ground_truth.json")
    gt_comments = load_ground_truth("comments_ground_truth.json")
    gt_pairs = load_ground_truth("duplicate_pairs_ground_truth.json")
    nlp_cache = load_nlp_cache()

    report: dict = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": "production_current",  # data_source.is_demo_mode() decides real vs demo underneath
        "modules_run": [module] if module != "all" else MODULES,
    }
    if module in ("all", "scraper"):
        report["scraper"] = run_scraper_module(dfs, gt_posts, gt_comments, gt_pairs)
    if module in ("all", "metrics"):
        report["metrics"] = run_metrics_module()
    if module in ("all", "nlp"):
        report["nlp"] = run_nlp_module(nlp_cache)
    if module in ("all", "comparison"):
        report["comparison"] = run_comparison_module()

    scorecard = build_scorecard(report)
    report["scorecard"] = scorecard
    report["limitations"] = LIMITATIONS

    tracked = regression.flatten_metrics(report)
    baseline = regression.load_baseline()
    report["regression"] = regression.compare_to_baseline(tracked, baseline)
    report["sample_sizes"] = {
        "posts": len(dfs["content"]), "comments": len(dfs["comments"]), "profiles": len(dfs["profiles"]),
    }
    return report


def build_scorecard(report: dict) -> list[dict]:
    """Flat list of (category, metric, value, status) -- spec section 29:
    separate categories, never one blended overall accuracy (section 30)."""
    rows = []

    def add(category: str, metric: str, label: str, value: float | None):
        rows.append({"category": category, "metric": metric, "label": label, "value": value,
                     "status": status_for(category, metric, value)})

    scraper = report.get("scraper", {})
    add("data", "completeness_pct", "Data Completeness",
        scraper.get("completeness", {}).get("content", {}).get("record_completeness", {}).get("completeness_pct"))
    add("data", "field_accuracy_pct", "Field Accuracy",
        scraper.get("field_accuracy", {}).get("posts", {}).get("overall_field_accuracy_pct"))
    add("data", "data_quality_pct", "Data Quality",
        scraper.get("data_quality", {}).get("content", {}).get("data_quality_pct"))
    add("data", "duplicate_f1", "Duplicate Detection F1",
        scraper.get("duplicates", {}).get("f1"))

    metrics = report.get("metrics", {})
    add("analytics", "metric_accuracy_pct", "Engagement/Rate/Average/Median Accuracy",
        _combined_pct_from_cases(metrics.get("engagement"), metrics.get("engagement_rate"),
                                  metrics.get("average_median")) if metrics else None)
    add("analytics", "activity_accuracy_pct", "Activity Accuracy",
        _pct_from_cases(metrics.get("activity", {})) if metrics.get("activity") else None)

    comparison = report.get("comparison", {}).get("comparison", {})
    add("analytics", "comparison_accuracy_pct", "Comparison Validation",
        _pct_from_cases(comparison) if comparison else None)

    nlp = report.get("nlp", {})
    add("nlp", "sentiment_f1", "Sentiment Macro F1", nlp.get("sentiment", {}).get("macro_f1"))
    add("nlp", "narrative_f1", "Narrative Macro F1", nlp.get("narrative", {}).get("macro_f1"))
    add("nlp", "comment_theme_f1", "Comment Theme Macro F1", nlp.get("comment_theme", {}).get("macro_f1"))
    add("nlp", "issue_f1", "Issue Detection Macro F1", nlp.get("issues", {}).get("macro_f1"))

    return rows


def print_console_report(report: dict, scorecard: list[dict], sample_sizes: dict, regression_result: dict | None) -> None:
    W = 72
    print("=" * W)
    print("POLITICAL SOCIAL MEDIA SYSTEM EVALUATION")
    print("=" * W)
    print(f"Run: {report['run_id']}   Dataset: {report['dataset_version']}")
    print(f"Records: {sample_sizes['posts']} posts, {sample_sizes['comments']} comments, "
          f"{sample_sizes['profiles']} profile snapshots")
    print()

    by_category: dict[str, list[dict]] = {}
    for row in scorecard:
        by_category.setdefault(row["category"], []).append(row)

    labels = {"data": "DATA QUALITY", "analytics": "METRICS", "nlp": "NLP"}
    for cat in ("data", "analytics", "nlp"):
        print("---")
        print(labels[cat])
        for row in by_category.get(cat, []):
            val = row["value"]
            val_str = "N/A" if val is None else (f"{val:.1f}%" if abs(val) > 1.5 else f"{val:.3f}")
            print(f"{row['label']:<38} {val_str:>10}   {row['status']}")
    print()

    if regression_result and regression_result.get("has_baseline"):
        print("---")
        print("REGRESSION")
        any_regression = False
        for name, r in regression_result["metrics"].items():
            if r["status"] == "REGRESSION":
                any_regression = True
                print(f"{name}: {r['baseline']} -> {r['current']}  ({r['diff']:+})  REGRESSION")
        if not any_regression:
            print("No regression detected.")
    print("=" * W)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the evaluation suite against the production system.")
    parser.add_argument("--module", choices=["all", *MODULES], default="all")
    parser.add_argument("--save-baseline", action="store_true",
                         help="Store this run's tracked metrics as the new regression baseline.")
    parser.add_argument("--out", default=None, help="Report basename under evaluation/reports/.")
    args = parser.parse_args(argv)

    report = build_report(args.module, run_id=args.out)

    if args.save_baseline:
        regression.save_as_baseline(regression.flatten_metrics(report))
        print("Saved current run's tracked metrics as the new regression baseline.")

    print_console_report(report, report["scorecard"], report["sample_sizes"], report["regression"])

    json_path = write_json_report(report["run_id"], report)
    csv_path = write_csv_report(f"{report['run_id']}_scorecard", report["scorecard"])
    print(f"\nJSON report: {json_path}")
    if csv_path:
        print(f"CSV scorecard: {csv_path}")

    any_fail = any(row["status"] == "FAIL" for row in report["scorecard"])
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
