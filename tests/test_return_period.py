from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from conftest import write_history

from glofas_ewds import (
    annual_maxima,
    discharge_by_day,
    discharge_series,
    gumbel_fit,
    return_level,
    return_levels,
)

RIVER = (11.82, 44.3)  # -> cell (11.875, 44.275)
SEA = (11.87, 44.27)  # -> cell (11.925, 44.275): masked


def test_the_fit_recovers_a_known_gumbel() -> None:
    rng = np.random.default_rng(7)
    sample = rng.gumbel(loc=100.0, scale=30.0, size=20_000)
    location, scale = gumbel_fit(sample)
    assert location == pytest.approx(100.0, rel=0.01)
    assert scale == pytest.approx(30.0, rel=0.02)


def test_the_fit_by_l_moments_by_hand() -> None:
    # x = 1, 2, 3: b0 = 2, b1 = (0*1 + 0.5*2 + 1*3) / 3 = 4/3, l2 = 2/3.
    location, scale = gumbel_fit([3.0, 1.0, 2.0])
    assert scale == pytest.approx((2 / 3) / math.log(2))
    assert location == pytest.approx(2 - 0.5772156649015329 * scale)


def test_the_two_year_level_is_the_median_of_the_maxima() -> None:
    # Gumbel: P(X <= x_2) = 1/2, so x_2 = location - scale * ln(ln 2).
    assert return_level(100.0, 30.0, 2) == pytest.approx(100.0 - 30.0 * math.log(math.log(2)))
    assert return_level(100.0, 30.0, 20) > return_level(100.0, 30.0, 5) > 100.0


def test_a_return_period_is_longer_than_a_year() -> None:
    with pytest.raises(ValueError, match="longer"):
        return_level(100.0, 30.0, 1)


def test_a_fit_needs_two_maxima() -> None:
    with pytest.raises(ValueError, match="two"):
        gumbel_fit([5.0])


def test_levels_need_enough_years() -> None:
    maxima = [100.0 + k for k in range(19)]
    assert return_levels(maxima) is None
    levels = return_levels([*maxima, 140.0])
    assert levels is not None
    assert list(levels) == [2, 5, 20]
    assert levels[2] < levels[5] < levels[20]
    assert return_levels([1.0, 2.0, 3.0], min_years=3, periods=(10,)) is not None


def test_a_dry_cell_has_no_levels() -> None:
    assert return_levels([0.0] * 30) is None
    assert return_levels([math.nan] * 30) is None


def test_annual_maxima_skip_incomplete_years() -> None:
    by_day = {date(2020, 1, 1) + timedelta(days=d): float(d % 400) for d in range(366 + 365 + 40)}
    by_day[date(2021, 3, 1)] = math.nan
    maxima = annual_maxima(by_day)
    assert list(maxima) == [2020, 2021]  # 2022 has 40 days only
    assert maxima[2020] == 365.0
    assert annual_maxima(by_day, min_days=30)[2022] == max(
        v for d, v in by_day.items() if d.year == 2022
    )


def test_by_day_keeps_the_day_and_drops_the_sea(tmp_path: Path) -> None:
    days = [date(2024, 5, 10), date(2024, 5, 11), date(2024, 5, 12)]
    values = [
        [[1.0, 9.0], [7.0, -9999.0]],
        [[1.0, 9.0], [-9999.0, -9999.0]],
        [[1.0, 9.0], [8.9, -9999.0]],
    ]
    write_history(tmp_path / "a.nc", days, values)
    # The same month again, as yesterday's partial file next to today's.
    write_history(tmp_path / "b.nc", days[:2], values[:2])
    files = [tmp_path / "a.nc", tmp_path / "b.nc"]
    by_day = discharge_by_day(files, [RIVER, SEA], start=days[0], end=days[-1])
    assert by_day[RIVER] == pytest.approx({days[0]: 7.0, days[2]: 8.9})
    assert by_day[SEA] == {}
    # discharge_series keeps its 0.1 behaviour: every value of every file.
    assert discharge_series(files, [RIVER], start=days[0], end=days[-1])[RIVER] == pytest.approx(
        [7.0, 8.9, 7.0]
    )
