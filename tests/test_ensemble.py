from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from conftest import FakeRetriever, write_cube, write_forecast

from glofas_ewds import (
    CONTROL,
    ENSEMBLE,
    EwdsClient,
    GlofasEwdsError,
    download_ensemble,
    download_forecast,
    ensemble_members,
    exceedance_by_lead,
    exceedance_probability,
    forecast_peaks,
    forecast_request,
)

RIVER = (11.82, 44.3)  # -> cell (11.875, 44.275): row 1, column 0
SEA = (11.87, 44.27)  # -> cell (11.925, 44.275): masked
OUTSIDE = (13.0, 44.3)

# Three members, two lead times, on the 2x2 grid of the fixtures.
M = -9999.0
CUBE = [
    [[[1.0, 9.0], [7.0, M]], [[1.0, 9.0], [12.0, M]]],
    [[[1.0, 9.0], [3.0, M]], [[1.0, 9.0], [4.0, M]]],
    [[[1.0, 9.0], [M, M]], [[1.0, 9.0], [M, M]]],  # a member masked on the river
]


def test_the_ensemble_request_names_the_perturbed_members() -> None:
    assert forecast_request(date(2026, 10, 10))["product_type"] == [CONTROL]
    r = forecast_request(date(2026, 10, 10), product=ENSEMBLE)
    assert r["product_type"] == ["ensemble_perturbed_forecasts"]


def test_the_ensemble_has_its_own_file(tmp_path: Path, retriever: FakeRetriever) -> None:
    control = download_forecast(tmp_path, date(2026, 10, 10), client=retriever)
    ens = download_ensemble(tmp_path, date(2026, 10, 10), client=retriever)
    download_ensemble(tmp_path, date(2026, 10, 10), client=retriever)
    assert (control.name, ens.name) == (
        "glofas_forecast_2026-10-10.nc",
        "glofas_ensemble_2026-10-10.nc",
    )
    assert [r["product_type"] for _, r in retriever.calls] == [[CONTROL], [ENSEMBLE]]


async def test_the_client_puts_the_ensemble_in_its_folder(
    tmp_path: Path, retriever: FakeRetriever
) -> None:
    path = await EwdsClient(tmp_path, retriever=retriever).ensemble(date(2026, 10, 10))
    assert path.parent == tmp_path / "ensemble"


@pytest.mark.parametrize(
    "dims",
    [
        ("number", "forecast_period", "forecast_reference_time", "latitude", "longitude"),
        ("forecast_period", "number", "forecast_reference_time", "latitude", "longitude"),
        ("forecast_reference_time", "number", "forecast_period", "latitude", "longitude"),
        ("number", "step", "latitude", "longitude"),
        ("realization", "forecast_period", "time", "latitude", "longitude"),
    ],
)
def test_members_are_read_by_dimension_name(tmp_path: Path, dims: tuple[str, ...]) -> None:
    path = tmp_path / "e.nc"
    write_cube(path, dims, CUBE)
    members = ensemble_members(path, [RIVER, SEA, OUTSIDE])
    assert list(members) == [RIVER]
    np.testing.assert_array_equal(members[RIVER], [[7.0, 12.0], [3.0, 4.0], [np.nan, np.nan]])
    assert forecast_peaks(path, [RIVER]) == {RIVER: 12.0}


def test_a_control_file_is_one_member(tmp_path: Path) -> None:
    path = tmp_path / "c.nc"
    write_forecast(path, [[[1.0, 9.0], [7.0, M]], [[1.0, 9.0], [12.5, M]]])
    np.testing.assert_array_equal(ensemble_members(path, [RIVER])[RIVER], [[7.0, 12.5]])


def test_four_unknown_dimensions_are_read_as_0_1_read_them(tmp_path: Path) -> None:
    # (lead time, run, lat, lon) by position, whatever the first two are called.
    path = tmp_path / "u.nc"
    write_cube(path, ("lead", "run", "latitude", "longitude"), [CUBE[0]])
    np.testing.assert_array_equal(ensemble_members(path, [RIVER])[RIVER], [[7.0, 12.0]])


def test_other_unknown_dimensions_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "x.nc"
    write_cube(path, ("number", "lead", "run", "latitude", "longitude"), CUBE)
    with pytest.raises(GlofasEwdsError, match="dimensions"):
        ensemble_members(path, [RIVER])


def test_two_runs_in_one_file_are_refused(tmp_path: Path) -> None:
    import netCDF4

    path = tmp_path / "r.nc"
    with netCDF4.Dataset(path, "w") as ds:
        for name, size in (("forecast_period", 1), ("forecast_reference_time", 2)):
            ds.createDimension(name, size)
        ds.createDimension("latitude", 2)
        ds.createDimension("longitude", 2)
        ds.createVariable("latitude", "f8", ("latitude",))[:] = [44.325, 44.275]
        ds.createVariable("longitude", "f8", ("longitude",))[:] = [11.875, 11.925]
        ds.createVariable(
            "dis24", "f4", ("forecast_period", "forecast_reference_time", "latitude", "longitude")
        )[:] = np.ones((1, 2, 2, 2))
    with pytest.raises(GlofasEwdsError, match="2 runs"):
        forecast_peaks(path, [RIVER])


def test_probability_is_the_share_of_members_whose_peak_reaches_the_threshold() -> None:
    members = [[7.0, 12.0], [3.0, 4.0], [10.0, 2.0], [np.nan, np.nan]]
    # The masked member does not vote: two of three.
    assert exceedance_probability(members, 10.0) == pytest.approx(2 / 3)
    assert exceedance_probability(members, 100.0) == 0.0
    assert exceedance_probability([[5.0, 6.0]], 6.0) == 1.0


@pytest.mark.parametrize("threshold", [None, 0.0, -1.0])
def test_no_threshold_is_no_probability(threshold: float | None) -> None:
    assert exceedance_probability([[5.0]], threshold) is None
    assert exceedance_by_lead([[5.0]], threshold) is None


def test_no_member_is_no_probability() -> None:
    assert exceedance_probability([[np.nan, np.nan]], 1.0) is None
    assert exceedance_by_lead(np.empty((0, 3)), 1.0) is None


def test_by_lead_says_when() -> None:
    members = [[1.0, 11.0, 12.0], [1.0, 2.0, 15.0], [1.0, np.nan, 3.0]]
    by_lead = exceedance_by_lead(members, 10.0)
    assert by_lead is not None
    assert by_lead[0] == 0.0
    assert by_lead[1] == pytest.approx(1 / 2)  # the NaN member does not vote on day 2
    assert by_lead[2] == pytest.approx(2 / 3)


def test_by_lead_with_a_lead_nobody_forecasts_is_nan() -> None:
    by_lead = exceedance_by_lead([[np.nan, 5.0], [np.nan, 1.0]], 2.0)
    assert by_lead is not None
    assert math.isnan(by_lead[0])
    assert by_lead[1] == 0.5
