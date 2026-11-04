"""GloFAS NetCDF files from the EWDS, read into numbers per node.

Needs the ``netcdf`` extra (``netCDF4``). No network.

Every reader takes your **nodes** (lon, lat points: river gauges, the centres
of a grid, your assets) and reads, for each, the cell
:func:`~glofas_ewds.cells.open_meteo_cell` chooses. What is not there stays
absent: a node outside the file or on a masked cell (sea, no river network)
gets no value, which is "no forecast here", never "the river is low".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from glofas_ewds._netcdf import netcdf4
from glofas_ewds.cells import Node, cell_indices, open_meteo_cell
from glofas_ewds.errors import GlofasEwdsError
from glofas_ewds.request import FORECAST_VARIABLE, HISTORICAL_VARIABLE


def _variable(ds: Any, name: str, path: Path) -> Any:
    try:
        return ds.variables[name]
    except KeyError as exc:
        raise GlofasEwdsError(f"{path.name}: no {name!r} variable") from exc


def discharge_series(
    files: Iterable[Path], nodes: Sequence[Node], *, start: date, end: date
) -> dict[Node, list[float]]:
    """Daily discharge (m³/s) of each node's cell between ``start`` and ``end``.

    The EWDS ``valid_time`` is the **end** of the 24 hours averaged, so the
    day after the one you asked for: the series is keyed by the day asked.
    Masked values are dropped, not zeroed.
    """
    nc = netcdf4()
    cells = [open_meteo_cell(lon, lat) for lon, lat in nodes]
    series: dict[Node, list[float]] = {n: [] for n in nodes}
    for path in files:
        with nc.Dataset(path) as ds:
            lats = np.asarray(_variable(ds, "latitude", path)[:], dtype=float)
            lons = np.asarray(_variable(ds, "longitude", path)[:], dtype=float)
            time = _variable(ds, "valid_time", path)
            converted: Any = nc.num2date(time[:], time.units, only_use_cftime_datetimes=False)
            instants = np.atleast_1d(converted)
            days = [datetime(t.year, t.month, t.day).date() - timedelta(days=1) for t in instants]
            keep = np.array([start <= d <= end for d in days])
            if not keep.any():
                continue
            iy, ix, inside = cell_indices(lats, lons, cells)
            data = np.ma.masked_invalid(_variable(ds, HISTORICAL_VARIABLE, path)[:])[keep]
            per_node = data[:, iy, ix]
            for k, node in enumerate(nodes):
                if inside[k]:
                    series[node].extend(float(v) for v in per_node[:, k].compressed())
    return series


def forecast_peaks(path: Path, nodes: Sequence[Node]) -> dict[Node, float]:
    """The highest forecast discharge (m³/s) in each node's cell, over all lead times.

    Nodes outside the file or on a masked cell are left out.
    """
    nc = netcdf4()
    cells = [open_meteo_cell(lon, lat) for lon, lat in nodes]
    with nc.Dataset(path) as ds:
        lats = np.asarray(_variable(ds, "latitude", path)[:], dtype=float)
        lons = np.asarray(_variable(ds, "longitude", path)[:], dtype=float)
        iy, ix, inside = cell_indices(lats, lons, cells)
        # (lead time, run, lat, lon): one run per file.
        data = np.ma.masked_invalid(_variable(ds, FORECAST_VARIABLE, path)[:])[:, 0]
        per_node = data[:, iy, ix]
    out: dict[Node, float] = {}
    for k, node in enumerate(nodes):
        values = per_node[:, k].compressed()
        if inside[k] and values.size:
            out[node] = float(values.max())
    return out


__all__ = ["discharge_series", "forecast_peaks"]
