from __future__ import annotations

import pytest

from glofas_ewds import cell_indices, declared_cell, open_meteo_cell


@pytest.mark.parametrize(
    ("node", "cell"),
    [
        # Coordinates Open-Meteo declared on 11 October 2026 (on the edge between
        # two cells it goes up for some points and down for others: float32),
        # plus the step east to the cell whose values it returns.
        ((11.9, 44.3), (11.925, 44.275)),
        ((12.0, 44.2), (12.025, 44.225)),
        ((16.6, 40.7), (16.675, 40.725)),
        ((7.7, 45.1), (7.725, 45.125)),
        ((15.6, 38.1), (15.675, 38.075)),
    ],
)
def test_the_cell_is_open_meteos(node: tuple[float, float], cell: tuple[float, float]) -> None:
    assert open_meteo_cell(*node) == pytest.approx(cell, abs=1e-3)


def test_the_served_cell_is_one_step_east_of_the_declared_one() -> None:
    lon, lat = declared_cell(11.9, 44.3)
    assert open_meteo_cell(11.9, 44.3) == pytest.approx((lon + 0.05, lat), abs=1e-9)


def test_indices_flag_cells_outside_the_file() -> None:
    iy, ix, inside = cell_indices(
        [44.325, 44.275], [11.875, 11.925], [(11.925, 44.275), (13.0, 44.32)]
    )
    assert iy.tolist() == [1, 0]
    assert ix.tolist() == [1, 1]
    assert inside.tolist() == [True, False]
