"""NARRATIVE EVALUATION (spec sections 18/19/20). Same shape as
sentiment.py -- human narrative_ground_truth.json vs the cached
MODEL-CLASSIFIED narrative, with per-category F1 (from
classification_report's per_class) and a confusion matrix, so weak
categories are visible rather than averaged away."""

from __future__ import annotations

from evaluation.metrics.classification import classification_report


def evaluate_narrative(ground_truth: list[dict], nlp_cache: dict) -> dict:
    """`ground_truth` entries: {"content_id", "human_label"}."""
    y_true, y_pred, errors = [], [], []
    models_used: set[str] = set()
    unclassified = 0

    for gt in ground_truth:
        cid, human = gt.get("content_id") or gt.get("record_id"), gt.get("human_label")
        if not cid or human is None:
            continue
        entry = nlp_cache.get(cid)
        if not entry or entry.get("narrative") is None:
            unclassified += 1
            continue
        predicted = entry["narrative"]
        y_true.append(human)
        y_pred.append(predicted)
        if entry.get("model"):
            models_used.add(entry["model"])
        if human != predicted:
            errors.append({"content_id": cid, "human_label": human, "model_label": predicted,
                            "confidence": entry.get("narrative_confidence"), "error_type": "wrong_class"})

    if not y_true:
        return {"n": 0, "unclassified": unclassified,
                "note": "no ground-truth narrative records have a cached model prediction yet -- "
                        "annotate narrative_ground_truth.json and run Run Analysis in the app first"}

    report = classification_report(y_true, y_pred)
    report["unclassified"] = unclassified
    report["models_used"] = sorted(models_used)
    report["errors"] = errors
    # Worst-performing categories first, so weak spots are immediately
    # visible (spec section 41) rather than buried in an alphabetical table.
    report["categories_worst_first"] = sorted(
        report["per_class"].items(), key=lambda kv: (kv[1]["f1"] if kv[1]["f1"] is not None else -1))
    return report
