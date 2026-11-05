"""GloFAS NetCDF files from the EWDS, read into numbers per node.

Needs the ``netcdf`` extra (``netCDF4``). No network.

Every reader takes your **nodes** (lon, lat points: river gauges, the centres
of a grid, your assets) and reads, for each, the cell
:func:`~glofas_ewds.cells.open_meteo_cell` chooses. What is not there stays
absent: a node outside the file or on a masked cell (sea, no river network)
gets no value, which is "no forecast here", never "the river is low".

Forecast files are read by the **names** of their dimensions (member, lead
time, run, latitude, longitude), not by their order, so the control run and
the ensemble share one reader. A file whose dimensions are not recognised
raises :class:`~glofas_ewds.errors.GlofasEwdsError` naming them.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from glofas_ewds._netcdf import netcdf4
from glofas_ewds.cells import Node, cell_indices, open_meteo_cell
from glofas_ewds.errors import GlofasEwdsError
from glofas_ewds.request import FORECAST_VARIABLE, HISTORICAL_VARIABLE

#: Names the EWDS (or a conversion of its files) may give each forecast axis.
_MEMBER = ("number", "realization", "ensemble_member")
_LEAD = ("forecast_period", "step", "leadtime")
_RUN = ("forecast_reference_time", "time")
_LAT = ("latitude",)
_LON = ("longitude",)


def _variable(ds: Any, name: str, path: Path) -> Any:
    try:
        return ds.variables[name]
    except KeyError as exc:
        raise GlofasEwdsError(f"{path.name}: no {name!r} variable") from exc


def _history_days(
    files: Iterable[Path], nodes: Sequence[Node], start: date, end: date
) -> Iterator[tuple[Node, list[date], np.ma.MaskedArray[Any, Any]]]:
    """For each file and node inside it: the days kept and the (masked) values."""
    nc = netcdf4()
    cells = [open_meteo_cell(lon, lat) for lon, lat in nodes]
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
            kept = [d for d, k in zip(days, keep, strict=True) if k]
            iy, ix, inside = cell_indices(lats, lons, cells)
            data = np.ma.masked_invalid(_variable(ds, HISTORICAL_VARIABLE, path)[:])[keep]
            per_node = data[:, iy, ix]
            for k, node in enumerate(nodes):
                if inside[k]:
                    yield node, kept, per_node[:, k]


def discharge_series(
    files: Iterable[Path], nodes: Sequence[Node], *, start: date, end: date
) -> dict[Node, list[float]]:
    """Daily discharge (m³/s) of each node's cell between ``start`` and ``end``.

    The EWDS ``valid_time`` is the **end** of the 24 hours averaged, so the
    day after the one you asked for: the series is keyed by the day asked.
    Masked values are dropped, not zeroed.
    """
    series: dict[Node, list[float]] = {n: [] for n in nodes}
    for node, _, values in _history_days(files, nodes, start, end):
        series[node].extend(float(v) for v in values.compressed())
    return series


def discharge_by_day(
    files: Iterable[Path], nodes: Sequence[Node], *, start: date, end: date
) -> dict[Node, dict[date, float]]:
    """Like :func:`discharge_series`, with each value under its day.

    What :func:`~glofas_ewds.return_period.annual_maxima` needs. A day in two
    files (yesterday's partial month next to today's) is kept once.
    """
    out: dict[Node, dict[date, float]] = {n: {} for n in nodes}
    for node, days, values in _history_days(files, nodes, start, end):
        masked = np.ma.getmaskarray(values)
        for day, value, gone in zip(days, values.data, masked, strict=True):
            if not gone:
                out[node][day] = float(value)
    return out


def _axis(dims: Sequence[str], names: tuple[str, ...]) -> int | None:
    found = [i for i, d in enumerate(dims) if d in names]
    return found[0] if found else None


def _forecast_cube(ds: Any, path: Path) -> npt.NDArray[Any]:
    """The forecast variable as a masked (member, lead, lat, lon) array."""
    var = _variable(ds, FORECAST_VARIABLE, path)
    dims = list(var.dimensions)
    data = np.ma.masked_invalid(var[:])
    named = [_axis(dims, n) for n in (_MEMBER, _LEAD, _RUN, _LAT, _LON)]
    if any(i is None for i in named[1:2] + named[3:]) or len(dims) != sum(
        i is not None for i in named
    ):
        if len(dims) == 4 and named[0] is None:
            # 0.1's reading, kept for files whose names we do not know:
            # (lead time, run, lat, lon), one run per file.
            return data[None, :, 0]
        raise GlofasEwdsError(f"{path.name}: {FORECAST_VARIABLE} has dimensions {tuple(dims)}")
    run = named[2]
    if run is not None:
        if data.shape[run] != 1:
            raise GlofasEwdsError(f"{path.name}: {data.shape[run]} runs in one file")
        data = np.ma.take(data, 0, axis=run)
        del dims[run]
    if _axis(dims, _MEMBER) is None:
        data = data[None]
        dims.insert(0, "number")
    order = [_axis(dims, n) for n in (_MEMBER, _LEAD, _LAT, _LON)]
    return np.ma.transpose(data, [i for i in order if i is not None])


def _forecast_per_node(path: Path, nodes: Sequence[Node]) -> dict[Node, npt.NDArray[np.float64]]:
    nc = netcdf4()
    cells = [open_meteo_cell(lon, lat) for lon, lat in nodes]
    with nc.Dataset(path) as ds:
        lats = np.asarray(_variable(ds, "latitude", path)[:], dtype=float)
        lons = np.asarray(_variable(ds, "longitude", path)[:], dtype=float)
        iy, ix, inside = cell_indices(lats, lons, cells)
        per_node = _forecast_cube(ds, path)[:, :, iy, ix]  # (member, lead, node)
    out: dict[Node, npt.NDArray[np.float64]] = {}
    for k, node in enumerate(nodes):
        values = np.ma.filled(per_node[:, :, k].astype(float), np.nan)
        if inside[k] and np.isfinite(values).any():
            out[node] = values
    return out


def forecast_peaks(path: Path, nodes: Sequence[Node]) -> dict[Node, float]:
    """The highest forecast discharge (m³/s) in each node's cell, over all lead
    times (and members, in an ensemble file).

    Nodes outside the file or on a masked cell are left out.
    """
    return {n: float(np.nanmax(v)) for n, v in _forecast_per_node(path, nodes).items()}


def ensemble_members(path: Path, nodes: Sequence[Node]) -> dict[Node, npt.NDArray[np.float64]]:
    """Each node's forecast as a (member, lead time) array in m³/s, NaN where masked.

    For a control file there is one member. Feed it to
    :func:`~glofas_ewds.ensemble.exceedance_probability`.
    """
    return _forecast_per_node(path, nodes)


__all__ = ["discharge_by_day", "discharge_series", "ensemble_members", "forecast_peaks"]
