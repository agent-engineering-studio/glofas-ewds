from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest
from conftest import write_fire, write_forecast, write_history

from glofas_ewds import GlofasEwdsError, discharge_series, fire_values, forecast_peaks

RIVER = (11.82, 44.3)  # -> cell (11.875, 44.275)
SEA = (11.87, 44.27)  # -> cell (11.925, 44.275): masked
OUTSIDE = (13.0, 44.3)


def test_series_reads_the_right_cell_and_drops_the_sea(tmp_path: Path) -> None:
    days = [date(2024, 5, 10), date(2024, 5, 11), date(2024, 5, 12)]
    path = tmp_path / "m.nc"
    write_history(
        path,
        days,
        [
            [[1.0, 9.0], [7.0, -9999.0]],
            [[1.0, 9.0], [6.0, -9999.0]],
            [[1.0, 9.0], [8.9, -9999.0]],
        ],
    )
    series = discharge_series(
        [path], [RIVER, SEA, OUTSIDE], start=date(2024, 5, 11), end=date(2024, 5, 12)
    )
    assert series[RIVER] == pytest.approx([6.0, 8.9])
    assert series[SEA] == []
    assert series[OUTSIDE] == []


def test_a_file_outside_the_window_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "m.nc"
    write_history(path, [date(2024, 1, 1)], [[[1.0, 1.0], [1.0, 1.0]]])
    assert discharge_series([path], [RIVER], start=date(2024, 5, 1), end=date(2024, 5, 2)) == {
        RIVER: []
    }


def test_the_peak_is_the_maximum_of_the_nodes_cell(tmp_path: Path) -> None:
    path = tmp_path / "p.nc"
    write_forecast(
        path,
        [
            [[1.0, 9.0], [7.0, -9999.0]],
            [[1.0, 9.0], [12.5, -9999.0]],
            [[1.0, 9.0], [8.0, -9999.0]],
        ],
    )
    assert forecast_peaks(path, [RIVER, SEA, OUTSIDE]) == {RIVER: pytest.approx(12.5)}


def test_a_file_without_the_variable_says_so(tmp_path: Path) -> None:
    path = tmp_path / "p.nc"
    write_history(path, [date(2024, 5, 10)], [[[1.0, 1.0], [1.0, 1.0]]])
    with pytest.raises(GlofasEwdsError, match="dis24"):
        forecast_peaks(path, [RIVER])


def test_fire_values_by_long_name_and_absent_outside(tmp_path: Path) -> None:
    path = tmp_path / "f.nc"
    days = [date(2025, 7, 1), date(2025, 7, 2)]
    nan = math.nan
    write_fire(path, days, [[[10.0, 20.0], [30.0, nan]], [[11.0, 21.0], [31.0, nan]]])
    matera = (16.55, 40.65)  # nearest (16.5, 40.75)
    sea = (16.5, 40.5)  # NaN cell
    far = (18.0, 40.6)
    out = fire_values([path], [matera, sea, far])
    assert out[(matera, date(2025, 7, 2))] == {"fwi": 21.0, "dc": 210.0, "bui": 42.0}
    assert (sea, date(2025, 7, 1)) not in out
    assert all(node != far for node, _ in out)
