import math

import pytest

from tremorlab.analysis.baseline import BASELINE_MIN_N, compare


def test_compare_none_below_three() -> None:
    assert BASELINE_MIN_N == 3
    assert compare(12.0, []) is None
    assert compare(12.0, [10.0, 10.0]) is None


def test_compare_percent() -> None:
    assert compare(12.0, [10.0, 10.0, 10.0]) == pytest.approx(20.0)


def test_compare_lower_value_is_negative() -> None:
    assert compare(8.0, [10.0, 12.0, 8.0]) == pytest.approx(-20.0)


def test_compare_custom_min_n() -> None:
    assert compare(5.0, [4.0], min_n=1) == pytest.approx(25.0)
    assert compare(5.0, [4.0, 4.0, 4.0], min_n=4) is None


def test_compare_zero_mean_is_none() -> None:
    assert compare(5.0, [0.0, 0.0, 0.0]) is None


def test_compare_ignores_non_finite_history() -> None:
    assert compare(12.0, [10.0, math.nan, 10.0]) is None
    assert compare(12.0, [10.0, math.nan, 10.0, 10.0]) == pytest.approx(20.0)


def test_compare_non_finite_value_is_none() -> None:
    assert compare(math.nan, [10.0, 10.0, 10.0]) is None
