from __future__ import annotations

import calendar
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np
import pytest

#: The 2x2 corner of the GloFAS grid near Faenza used by the tests:
#: [lat 44.325, lat 44.275] by [lon 11.875, lon 11.925].
LATS = [44.325, 44.275]
LONS = [11.875, 11.925]


def write_history(path: Path, days: Sequence[date], values: list[list[list[float]]]) -> None:
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("valid_time", len(days))
        ds.createDimension("latitude", 2)
        ds.createDimension("longitude", 2)
        t = ds.createVariable("valid_time", "i8", ("valid_time",))
        t.units = "seconds since 1970-01-01"
        # valid_time is the end of the 24 hours: the day after the one asked.
        t[:] = [calendar.timegm(d.timetuple()) + 86400 for d in days]
        ds.createVariable("latitude", "f8", ("latitude",))[:] = LATS
        ds.createVariable("longitude", "f8", ("longitude",))[:] = LONS
        v = ds.createVariable(
            "avg_dis", "f4", ("valid_time", "latitude", "longitude"), fill_value=-9999.0
        )
        v[:] = np.ma.masked_equal(np.array(values, dtype="f4"), -9999.0)


def write_forecast(path: Path, values: list[list[list[float]]]) -> None:
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("forecast_period", len(values))
        ds.createDimension("forecast_reference_time", 1)
        ds.createDimension("latitude", 2)
        ds.createDimension("longitude", 2)
        ds.createVariable("latitude", "f8", ("latitude",))[:] = LATS
        ds.createVariable("longitude", "f8", ("longitude",))[:] = LONS
        v = ds.createVariable(
            "dis24",
            "f4",
            ("forecast_period", "forecast_reference_time", "latitude", "longitude"),
            fill_value=-9999.0,
        )
        v[:] = np.ma.masked_equal(np.array(values, dtype="f4")[:, None, :, :], -9999.0)


def write_fire(path: Path, days: Sequence[date], fwi: list[list[list[float]]]) -> None:
    """An FWI file on a 0.25° grid with GRIB short names, as the EWDS writes it."""
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("valid_time", len(days))
        ds.createDimension("latitude", 2)
        ds.createDimension("longitude", 2)
        t = ds.createVariable("valid_time", "i8", ("valid_time",))
        t.units = "seconds since 1970-01-01"
        t[:] = [calendar.timegm(d.timetuple()) for d in days]
        ds.createVariable("latitude", "f8", ("latitude",))[:] = [40.75, 40.5]
        ds.createVariable("longitude", "f8", ("longitude",))[:] = [16.25, 16.5]
        dims = ("valid_time", "latitude", "longitude")
        arr = np.ma.masked_invalid(np.array(fwi, dtype="f4"))
        for short, long_name, scale in (
            ("fwinx", "Forest fire weather index", 1.0),
            ("drtcode", "Drought code", 10.0),
            ("fbupinx", "Fire buildup index", 2.0),
        ):
            v = ds.createVariable(short, "f4", dims, fill_value=np.float32(np.nan))
            v.long_name = long_name
            v[:] = arr * scale
        other = ds.createVariable("unrelated", "f4", ("latitude",))
        other.long_name = "Forest fire weather index, but not on the grid"
        other[:] = [0.0, 0.0]


class FakeRetriever:
    """Writes a file for each request and remembers what was asked."""

    def __init__(self, fail: Callable[[dict[str, Any]], Exception | None] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail

    def retrieve(self, name: str, request: dict[str, Any], target: str) -> None:
        self.calls.append((name, request))
        if self._fail is not None and (exc := self._fail(request)) is not None:
            raise exc
        Path(target).write_bytes(b"x")


@pytest.fixture
def retriever() -> FakeRetriever:
    return FakeRetriever()
