"""
DUPLICATE DETECTION EVALUATION (spec section 10).

Important, honest scoping note: backend/app/ingestion/dedupe.py's actual
rule is ID-equality -- two records are "the same" iff they share
(platform, content_id) (falling back to a content hash only when
content_id is itself missing, per dedupe.py's own docstring). It does
*not* do fuzzy/near-duplicate matching on caption or timestamp similarity.
So the "production prediction" this evaluator checks is exactly that real
rule: predicted_duplicate(pair) = (content_id_a == content_id_b).

This means a human-labeled duplicate pair with two *different* content_ids
(e.g. the same real-world post re-scraped under a different generated id)
will always score as a False Negative here -- correctly, because
production genuinely cannot catch that case. That's a real limitation to
report to a reviewer, not a bug in this evaluator.
"""

from __future__ import annotations

from evaluation.metrics.classification import precision_recall_f1


def production_predicts_duplicate(content_id_a: str, content_id_b: str) -> bool:
    """The actual rule backend/app/ingestion/dedupe.py applies (see this
    module's docstring) -- not a re-derived heuristic."""
    return content_id_a == content_id_b


def evaluate_duplicates(ground_truth_pairs: list[dict]) -> dict:
    if not ground_truth_pairs:
        return {"n_pairs": 0, "precision": None, "recall": None, "f1": None,
                "note": "no labeled pairs yet -- add records to duplicate_pairs_ground_truth.json"}

    tp = fp = fn = tn = 0
    errors: list[dict] = []
    for pair in ground_truth_pairs:
        a, b, expected = pair.get("content_id_a"), pair.get("content_id_b"), pair.get("is_duplicate")
        if a is None or b is None or expected is None:
            continue
        predicted = production_predicts_duplicate(a, b)
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
            errors.append({**pair, "predicted": predicted, "error_type": "false_positive"})
        elif not predicted and expected:
            fn += 1
            errors.append({**pair, "predicted": predicted, "error_type": "false_negative"})
        else:
            tn += 1

    stats = precision_recall_f1(tp, fp, fn)
    stats["tn"] = tn
    stats["n_pairs"] = tp + fp + fn + tn
    stats["errors"] = errors
    return stats
