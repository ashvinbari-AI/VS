"""
Shared classification-metric primitives used by every evaluator that
compares production output against ground-truth labels (sentiment,
narrative, comment theme, issues, duplicates, content type).

Pure Python + stdlib -- no scikit-learn/scipy dependency, so these run in
the same environment the backend already uses. Every ratio here is
safe-divide: a zero denominator returns None (never ZeroDivisionError, NaN,
or a fabricated 0), matching this project's "never invent a value" rule
(see backend/app/analytics/engine.py's own docstring for the same
convention on the production side).
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Callable, Hashable, Sequence


def safe_divide(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def _r(x: float | None, digits: int = 4) -> float | None:
    return round(x, digits) if isinstance(x, (int, float)) else x


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict:
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": _r(precision), "recall": _r(recall), "f1": _r(f1),
            "tp": tp, "fp": fp, "fn": fn}


def confusion_matrix(y_true: Sequence[Hashable], y_pred: Sequence[Hashable],
                      labels: Sequence[Hashable] | None = None) -> dict:
    """{"labels": [...], "matrix": {actual_label: {predicted_label: count}}}."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    if labels is None:
        labels = sorted({*y_true, *y_pred}, key=str)
    matrix = {a: {p: 0 for p in labels} for a in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return {"labels": list(labels), "matrix": matrix}


def classification_report(y_true: Sequence[Hashable], y_pred: Sequence[Hashable],
                           labels: Sequence[Hashable] | None = None) -> dict:
    """Per-class precision/recall/F1/support, overall accuracy, and
    macro/weighted aggregates. y_true/y_pred must be row-aligned (same
    item, same position) sequences of single labels -- for multi-label
    tasks (e.g. issues) use `multilabel_micro_macro` instead."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    if labels is None:
        labels = sorted({*y_true, *y_pred}, key=str)
    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = safe_divide(correct, n)

    supports = Counter(y_true)
    per_class = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        stats = precision_recall_f1(tp, fp, fn)
        stats["support"] = supports.get(label, 0)
        per_class[label] = stats

    f1s = [c["f1"] for c in per_class.values() if c["f1"] is not None]
    macro_f1 = round(sum(f1s) / len(f1s), 4) if f1s else None
    precisions = [c["precision"] for c in per_class.values() if c["precision"] is not None]
    recalls = [c["recall"] for c in per_class.values() if c["recall"] is not None]
    macro_precision = round(sum(precisions) / len(precisions), 4) if precisions else None
    macro_recall = round(sum(recalls) / len(recalls), 4) if recalls else None

    total_support = sum(c["support"] for c in per_class.values())
    weighted_f1 = None
    if total_support:
        weighted_f1 = round(
            sum((c["f1"] or 0) * c["support"] for c in per_class.values()) / total_support, 4)

    return {
        "n": n, "accuracy": _r(accuracy),
        "macro_precision": macro_precision, "macro_recall": macro_recall, "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels),
    }


def multilabel_micro_macro(y_true_sets: Sequence[set], y_pred_sets: Sequence[set],
                            labels: Sequence[Hashable] | None = None) -> dict:
    """Multi-label evaluation (issue detection: one item can carry several
    labels at once). Each element of y_true_sets/y_pred_sets is a *set* of
    labels for that item, not a single label."""
    if len(y_true_sets) != len(y_pred_sets):
        raise ValueError("y_true_sets and y_pred_sets must be the same length")
    if labels is None:
        labels = sorted({l for s in y_true_sets for l in s} | {l for s in y_pred_sets for l in s}, key=str)

    micro_tp = micro_fp = micro_fn = 0
    per_label = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true_sets, y_pred_sets) if label in t and label in p)
        fp = sum(1 for t, p in zip(y_true_sets, y_pred_sets) if label not in t and label in p)
        fn = sum(1 for t, p in zip(y_true_sets, y_pred_sets) if label in t and label not in p)
        per_label[label] = precision_recall_f1(tp, fp, fn)
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

    micro = precision_recall_f1(micro_tp, micro_fp, micro_fn)
    f1s = [c["f1"] for c in per_label.values() if c["f1"] is not None]
    macro_f1 = round(sum(f1s) / len(f1s), 4) if f1s else None

    return {
        "micro_precision": micro["precision"], "micro_recall": micro["recall"], "micro_f1": micro["f1"],
        "macro_f1": macro_f1, "per_label": per_label,
    }


def cohens_kappa(rater_a: Sequence[Hashable], rater_b: Sequence[Hashable]) -> float | None:
    """Inter-annotator agreement between two humans labeling the same
    items, corrected for chance agreement -- NOT a model-quality metric.
    None if the raters didn't label the same number of items, or labeled
    nothing at all."""
    if len(rater_a) != len(rater_b) or not rater_a:
        return None
    n = len(rater_a)
    labels = sorted({*rater_a, *rater_b}, key=str)
    observed = sum(1 for a, b in zip(rater_a, rater_b) if a == b) / n
    count_a = Counter(rater_a)
    count_b = Counter(rater_b)
    expected = sum((count_a.get(l, 0) / n) * (count_b.get(l, 0) / n) for l in labels)
    if expected >= 1:
        return 1.0 if observed >= 1 else 0.0
    return round((observed - expected) / (1 - expected), 4)


def bootstrap_ci(y_true: Sequence, y_pred: Sequence, metric_fn: Callable[[Sequence, Sequence], float | None],
                  n_boot: int = 1000, seed: int = 42, confidence: float = 0.95) -> dict:
    """Confidence interval for a metric via resampling with replacement
    (spec section 63/64). `metric_fn(y_true_sample, y_pred_sample)` must
    return a single float (or None). Deterministic given a fixed seed, so
    two runs over the same data reproduce the same interval."""
    n = len(y_true)
    if n == 0:
        return {"point_estimate": None, "lower": None, "upper": None, "n_boot": n_boot, "confidence": confidence}
    rng = random.Random(seed)
    point = metric_fn(y_true, y_pred)
    samples: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        try:
            val = metric_fn([y_true[i] for i in idx], [y_pred[i] for i in idx])
        except Exception:
            continue
        if val is not None:
            samples.append(val)
    samples.sort()
    if not samples:
        return {"point_estimate": _r(point), "lower": None, "upper": None,
                "n_boot": n_boot, "confidence": confidence}
    lower_idx = int((1 - confidence) / 2 * len(samples))
    upper_idx = min(int((1 - (1 - confidence) / 2) * len(samples)), len(samples) - 1)
    return {
        "point_estimate": _r(point), "lower": _r(samples[lower_idx]), "upper": _r(samples[upper_idx]),
        "n_boot": n_boot, "confidence": confidence,
    }
