"""The official Copernicus Fire Weather Index from the EWDS.

``cems-fire-historical-v1`` is the Canadian FWI system computed by Copernicus
on ERA5, from 1940 to a few days ago, at 0.25°. Put next to your own FWI it
tells you whether your chain drifts (spin-up, rain, observation hour).

The request builder is pure; :func:`fire_values` needs the ``netcdf`` extra.

Two traps. In the NetCDF the variables carry GRIB short names (``fwinx``,
``drtcode``, ...), not the names you asked for, so they are recognised here by
their ``long_name``. And the build-up index is called "Fire buildup index" in
the file, not "Build up index" as in the request.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

import numpy as np

from glofas_ewds._netcdf import netcdf4
from glofas_ewds.cells import Node, cell_indices
from glofas_ewds.request import ITALY, Area

FIRE_DATASET: Final = "cems-fire-historical-v1"
FIRE_VERSION: Final = "4_1"
#: The finest grid the dataset offers.
FIRE_GRID_STEP: Final = 0.25

#: Component -> (variable to request, start of its ``long_name`` in the file).
FIRE_VARIABLES: Final[dict[str, tuple[str, str]]] = {
    "fwi": ("fire_weather_index", "forest fire weather index"),
    "ffmc": ("fine_fuel_moisture_code", "fine fuel moisture code"),
    "dmc": ("duff_moisture_code", "duff moisture code"),
    "dc": ("drought_code", "drought code"),
    "isi": ("initial_fire_spread_index", "initial fire spread index"),
    "bui": ("build_up_index", "fire buildup index"),
}


def fire_request(
    year: int,
    month: int,
    days: list[str],
    *,
    product: str = "consolidated_dataset",
    area: Area = ITALY,
) -> dict[str, Any]:
    """The six FWI components for ``days`` of one month; ``product`` is
    ``consolidated_dataset`` or ``intermediate_dataset``."""
    return {
        "product_type": "reanalysis",
        "variable": [v for v, _ in FIRE_VARIABLES.values()],
        "dataset_type": product,
        "system_version": [FIRE_VERSION],
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": days,
        "grid": f"{FIRE_GRID_STEP}/{FIRE_GRID_STEP}",
        "data_format": "netcdf",
        "area": list(area),
    }


def _days(time: Any, nc: Any) -> list[date]:
    units = getattr(time, "units", "seconds since 1970-01-01")
    converted: Any = nc.num2date(time[:], units, only_use_cftime_datetimes=False)
    return [datetime(t.year, t.month, t.day).date() for t in np.atleast_1d(converted)]


def fire_values(
    paths: Iterable[Path], nodes: Sequence[Node]
) -> dict[tuple[Node, date], dict[str, float]]:
    """For each (node, day), the FWI components of the node's cell.

    A cell without data (sea, outside the file) gives no row: absent, not zero.
    """
    nc = netcdf4()
    out: dict[tuple[Node, date], dict[str, float]] = {}
    for path in paths:
        with nc.Dataset(path) as ds:
            lats = np.asarray(ds.variables["latitude"][:], dtype=float)
            lons = np.asarray(ds.variables["longitude"][:], dtype=float)
            days = _days(ds.variables["valid_time"], nc)
            by_name = {
                getattr(v, "long_name", "").lower(): v
                for v in ds.variables.values()
                if v.dimensions == ("valid_time", "latitude", "longitude")
            }
            columns: dict[str, Any] = {}
            for component, (_, name_start) in FIRE_VARIABLES.items():
                for name, v in by_name.items():
                    if name.startswith(name_start):
                        columns[component] = np.ma.filled(np.ma.asarray(v[:], dtype=float), np.nan)
            iy, ix, inside = cell_indices(lats, lons, nodes, step=FIRE_GRID_STEP)
            for k, node in enumerate(nodes):
                if not inside[k]:
                    continue
                for t, day in enumerate(days):
                    values = {
                        c: float(a[t, iy[k], ix[k]])
                        for c, a in columns.items()
                        if np.isfinite(a[t, iy[k], ix[k]])
                    }
                    if values:
                        out[(node, day)] = values
    return out


__all__ = [
    "FIRE_DATASET",
    "FIRE_GRID_STEP",
    "FIRE_VARIABLES",
    "FIRE_VERSION",
    "fire_request",
    "fire_values",
]
