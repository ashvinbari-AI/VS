"""SYNTHETIC TEST DATA. [10, 20, 30, 40, 50] -- mean=30, median=30,
hand-checkable by inspection (spec section 13's own example)."""

from __future__ import annotations

from evaluation.metrics.stats import (
    independent_mean, independent_median, independent_percentile,
    percentage_difference, within_tolerance,
)

_VALUES = [10, 20, 30, 40, 50]


def test_independent_mean():
    assert independent_mean(_VALUES) == 30.0


def test_independent_median():
    assert independent_median(_VALUES) == 30.0


def test_independent_mean_ignores_none():
    assert independent_mean([10, None, 20, None, 30]) == 20.0


def test_independent_mean_all_none_returns_none():
    assert independent_mean([None, None]) is None


def test_independent_percentile_p90_matches_pandas_linear_interpolation():
    # pandas .quantile(0.90) on [10,20,30,40,50] with linear interpolation:
    # pos = 0.9*4 = 3.6 -> 40 + 0.6*(50-40) = 46.0
    assert independent_percentile(_VALUES, 0.90) == 46.0


def test_independent_percentile_single_value():
    assert independent_percentile([42], 0.5) == 42.0


def test_independent_percentile_empty():
    assert independent_percentile([], 0.5) is None


def test_percentage_difference_normal():
    assert percentage_difference(120, 100) == 20.0


def test_percentage_difference_zero_denominator_is_none_not_infinity():
    assert percentage_difference(120, 0) is None


def test_percentage_difference_missing_value_is_none():
    assert percentage_difference(None, 100) is None


def test_within_tolerance_both_none_agree():
    assert within_tolerance(None, None) is True


def test_within_tolerance_none_vs_number_disagree():
    assert within_tolerance(None, 5) is False
    assert within_tolerance(5, None) is False


def test_within_tolerance_rounding_wobble():
    assert within_tolerance(10.001, 10.002, abs_tol=0.01) is True
    assert within_tolerance(10.0, 10.5, abs_tol=0.01) is False
