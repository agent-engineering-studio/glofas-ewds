from __future__ import annotations

import pytest

from glofas_ewds import MIN_REFERENCE_DAYS, discharge_ratio, percentile, references


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert percentile([5.0], 0.9) == 5.0
    assert percentile([], 0.9) is None


def test_a_reference_needs_a_year_of_days() -> None:
    long = [float(k) for k in range(400)]
    ref = references({"a": long, "b": [5.0] * 10}, p=0.9)
    assert ref["a"] == pytest.approx(359.1)
    assert ref["b"] is None
    assert MIN_REFERENCE_DAYS == 365


def test_min_days_is_yours_to_choose() -> None:
    assert references({"b": [5.0] * 10}, min_days=10) == {"b": 5.0}


def test_ratio_says_i_dont_know_rather_than_low() -> None:
    assert discharge_ratio(30.0, 10.0) == 3.0
    assert discharge_ratio(None, 10.0) is None
    assert discharge_ratio(30.0, None) is None
    assert discharge_ratio(30.0, 0.0) is None
