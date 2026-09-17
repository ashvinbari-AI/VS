"""ISSUE DETECTION EVALUATION (spec section 22) -- multi-label: a comment
can legitimately mention several issues at once ("Roads are damaged and
there is no water" -> ["Roads", "Water"] is a full match, not a partial
one). Uses micro/macro precision/recall/F1 via
metrics.classification.multilabel_micro_macro, never forcing a single
label."""

from __future__ import annotations

from evaluation.metrics.classification import multilabel_micro_macro


def evaluate_issues(ground_truth: list[dict], nlp_cache: dict) -> dict:
    """`ground_truth` entries: {"record_id", "human_issues": [...]}."""
    y_true_sets, y_pred_sets, errors = [], [], []
    unclassified = 0

    for gt in ground_truth:
        rid, human = gt.get("record_id") or gt.get("comment_id"), gt.get("human_issues")
        if not rid or human is None:
            continue
        entry = nlp_cache.get(f"comment:{rid}") or nlp_cache.get(rid)
        if not entry or entry.get("issues") is None:
            unclassified += 1
            continue
        predicted = set(entry["issues"])
        expected = set(human)
        y_true_sets.append(expected)
        y_pred_sets.append(predicted)
        if predicted != expected:
            errors.append({"record_id": rid, "human_issues": sorted(expected),
                            "model_issues": sorted(predicted),
                            "missed": sorted(expected - predicted), "extra": sorted(predicted - expected)})

    if not y_true_sets:
        return {"n": 0, "unclassified": unclassified,
                "note": "no ground-truth issue records have a cached model prediction yet"}

    report = multilabel_micro_macro(y_true_sets, y_pred_sets)
    report["n"] = len(y_true_sets)
    report["unclassified"] = unclassified
    report["errors"] = errors
    return report
