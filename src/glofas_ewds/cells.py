"""Which GloFAS cell a point reads, and where that cell is in a file.

Pure: nothing here does I/O.

GloFAS 4 is a regular grid of 0.05° (about 5 km) cells. Along a river two
neighbouring cells can differ by an order of magnitude: one holds the main
channel, the next a side valley. Picking the wrong one is the most expensive
mistake you can make with this data, and nothing raises when you make it.

Two facts, both measured on 11 October 2026 on 28 real nodes in Italy:

* Open-Meteo picks the cell for a point in **float32**, rounding **away from
  zero** from an origin at -59.975 / -180.025. On the edge between two cells
  this goes up for some points and down for others.
* The values Open-Meteo returns for that cell are the ones the EWDS labels
  **one step east**. With the shift, 28 nodes out of 28 match the EWDS
  (consolidated history and forecast alike); without it, 0 out of 28. On the
  Toce that is 2 m³/s against 22. Comparing the coordinates Open-Meteo
  *declares* does not show it.

:func:`open_meteo_cell` gives the EWDS cell whose numbers Open-Meteo serves for
a point, so a reference computed from the EWDS and a forecast read from
Open-Meteo talk about the same water.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

import numpy as np
import numpy.typing as npt

#: Grid step of GloFAS 4, in degrees.
GRID_STEP: Final = 0.05
#: The grid origin Open-Meteo rounds from.
ORIGIN_LAT: Final = -59.975
ORIGIN_LON: Final = -180.025

#: Longitude, latitude in degrees.
Node = tuple[float, float]


def _round_half_away(x: float) -> int:
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _axis(value: float, origin: float) -> float:
    f = np.float32
    i = _round_half_away(float((f(value) - f(origin)) / f(GRID_STEP)))
    return round(float(f(origin) + f(i) * f(GRID_STEP)), 3)


def declared_cell(longitude: float, latitude: float) -> Node:
    """The cell Open-Meteo *declares* in its answer for a point.

    This is not the cell whose values it returns: see :func:`open_meteo_cell`.
    """
    return _axis(longitude, ORIGIN_LON), _axis(latitude, ORIGIN_LAT)


def open_meteo_cell(longitude: float, latitude: float) -> Node:
    """The EWDS cell (lon, lat) whose values Open-Meteo returns for a point.

    The declared cell moved one step east.
    """
    lon, lat = declared_cell(longitude, latitude)
    return round(lon + GRID_STEP, 3), lat


def cell_indices(
    latitudes: npt.ArrayLike,
    longitudes: npt.ArrayLike,
    cells: Sequence[Node],
    *,
    step: float = GRID_STEP,
) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.intp], npt.NDArray[np.bool_]]:
    """Row, column and "inside the file" for each cell, on a file's axes.

    Outside the area you downloaded the nearest point is the edge, which is
    not the cell: those come back with ``inside`` False.
    """
    lats = np.asarray(latitudes, dtype=float)
    lons = np.asarray(longitudes, dtype=float)
    iy = np.array([int(np.abs(lats - lat).argmin()) for _, lat in cells], dtype=np.intp)
    ix = np.array([int(np.abs(lons - lon).argmin()) for lon, _ in cells], dtype=np.intp)
    want_lat = np.array([c[1] for c in cells], dtype=float)
    want_lon = np.array([c[0] for c in cells], dtype=float)
    inside = (np.abs(lats[iy] - want_lat) < step / 2) & (np.abs(lons[ix] - want_lon) < step / 2)
    return iy, ix, inside


__all__ = [
    "GRID_STEP",
    "ORIGIN_LAT",
    "ORIGIN_LON",
    "Node",
    "cell_indices",
    "declared_cell",
    "open_meteo_cell",
]
