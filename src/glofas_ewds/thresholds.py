"""The official GloFAS v4 flood thresholds: the 2-, 5- and 20-year flow of a cell.

:func:`threshold_url` and :func:`threshold_file_name` are pure; the readers
need the ``netcdf`` extra. No network: download the files with your own client.

The EWDS does not serve the thresholds. ECMWF publishes them as "GloFAS
auxiliary data": three global NetCDF files at 0.05° (about 165 MB each), public
and without credentials, one per return period. For each node the readers take
the cell the node already reads for the forecast and the reference, the one
:func:`~glofas_ewds.cells.open_meteo_cell` chooses: a wrong cell on a river is
a factor of ten.

Compare with :func:`~glofas_ewds.return_period.return_levels`, which fits your
own levels from a node's reanalysis: these are the official ones.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np

from glofas_ewds._netcdf import netcdf4
from glofas_ewds.cells import Node, cell_indices, open_meteo_cell
from glofas_ewds.errors import GlofasEwdsError

#: Where ECMWF publishes the file of each return period.
THRESHOLD_URL: Final = "https://confluence.ecmwf.int/download/attachments/242067380/{name}"


def threshold_file_name(years: int) -> str:
    """The name ECMWF gives the file of the ``years``-year flood."""
    return f"flood_threshold_glofas_v4_rl_{float(years):.1f}.nc"


def threshold_url(years: int) -> str:
    """The public URL of the file of the ``years``-year flood."""
    return THRESHOLD_URL.format(name=threshold_file_name(years))


def _grid(ds: Any, path: Path) -> tuple[Any, Any, Any]:
    """The only 2-D variable of the file, and its latitudes and longitudes."""
    variables = ds.variables
    names = [k for k, v in variables.items() if v.ndim == 2]
    if len(names) != 1:
        raise GlofasEwdsError(f"{path.name}: expected one 2-D variable, found {names}")
    try:
        lat = next(v for k, v in variables.items() if k.lower().startswith("lat"))
        lon = next(v for k, v in variables.items() if k.lower().startswith("lon"))
    except StopIteration as exc:
        raise GlofasEwdsError(f"{path.name}: no latitude or longitude variable") from exc
    return variables[names[0]], lat, lon


def read_threshold(path: Path, nodes: Sequence[Node]) -> list[float | None]:
    """The threshold (m³/s) of one file in each node's cell, in the order of ``nodes``.

    ``None`` for a node outside the file or on a cell that is masked or not
    positive (sea, no river network). Only the rectangle that contains the
    nodes is read: the file is the world.
    """
    if not nodes:
        return []
    nc = netcdf4()
    with nc.Dataset(path) as ds:
        var, lat, lon = _grid(ds, path)
        lats = np.asarray(lat[:], dtype=float)
        lons = np.asarray(lon[:], dtype=float)
        cells = [open_meteo_cell(x, y) for x, y in nodes]
        rows, cols, inside = cell_indices(lats, lons, cells)
        r0, r1 = int(rows.min()), int(rows.max()) + 1
        c0, c1 = int(cols.min()), int(cols.max()) + 1
        block = np.ma.filled(np.ma.asarray(var[r0:r1, c0:c1], dtype=float), np.nan)
    out: list[float | None] = []
    for r, c, ok in zip(rows, cols, inside, strict=True):
        v = float(block[r - r0, c - c0]) if ok else float("nan")
        out.append(v if np.isfinite(v) and v > 0 else None)
    return out


def flood_thresholds(
    files: Mapping[int, Path], nodes: Sequence[Node]
) -> dict[Node, dict[int, float | None]]:
    """``{node: {years: m³/s}}`` from ``{years: file}``.

    Each node's value is what :func:`~glofas_ewds.return_period.flood_label`
    takes as ``thresholds``.
    """
    columns = {years: read_threshold(path, nodes) for years, path in files.items()}
    return {n: {years: col[i] for years, col in columns.items()} for i, n in enumerate(nodes)}


__all__ = [
    "THRESHOLD_URL",
    "flood_thresholds",
    "read_threshold",
    "threshold_file_name",
    "threshold_url",
]
