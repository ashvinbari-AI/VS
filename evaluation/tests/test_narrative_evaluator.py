"""SYNTHETIC TEST DATA."""

from __future__ import annotations

from evaluation.evaluators.narrative import evaluate_narrative


def test_worst_category_sorted_first():
    # Infrastructure: 3 true, 2 correct, 1 misclassified as Farmers -> decent F1.
    # Healthcare: 3 true, 1 correct, 2 misclassified as Farmers -> worse F1.
    # Farmers: 1 true, correctly predicted, but inflated by 3 false positives
    # borrowed from the above misclassifications -> worst F1 of the three.
    gt = [{"content_id": f"i{i}", "human_label": "Infrastructure"} for i in range(3)] + \
         [{"content_id": f"h{i}", "human_label": "Healthcare"} for i in range(3)] + \
         [{"content_id": "f1", "human_label": "Farmers"}]
    cache = {
        "i0": {"narrative": "Infrastructure"}, "i1": {"narrative": "Infrastructure"},
        "i2": {"narrative": "Farmers"},
        "h0": {"narrative": "Healthcare"}, "h1": {"narrative": "Farmers"}, "h2": {"narrative": "Farmers"},
        "f1": {"narrative": "Farmers"},
    }
    report = evaluate_narrative(gt, cache)
    worst_first = report["categories_worst_first"]
    f1s = [f1 for _, stats in worst_first if (f1 := stats["f1"]) is not None]
    # The defining property of "worst first": F1 values are non-decreasing
    # down the list, and the single lowest F1 present is the first entry.
    assert f1s == sorted(f1s)
    assert worst_first[0][1]["f1"] == min(f1s)


def test_accepts_record_id_key_as_alias_for_content_id():
    gt = [{"record_id": "p1", "human_label": "Farmers"}]
    cache = {"p1": {"narrative": "Farmers"}}
    report = evaluate_narrative(gt, cache)
    assert report["accuracy"] == 1.0
