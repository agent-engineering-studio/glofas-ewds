"""Return levels of a river from its own GloFAS history: the 2-, 5-, 20-year flow.

Pure: nothing here does I/O.

The EWDS does not serve GloFAS's flood thresholds, and the 90th percentile of
two years (:func:`~glofas_ewds.reference.references`) is "an ordinary high
flow", not "a flood that comes once in five years". This module fits a Gumbel
distribution to the **annual maxima** of a node's reanalysis, by L-moments,
and reads the levels off it.

Two cautions. These are **not** the official GloFAS thresholds: same family
of method, but your years, your cells, your fit. And a fit needs decades: the
reanalysis starts in 1979, and fewer than ``min_years`` complete years give
``None``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Final

import numpy as np
import numpy.typing as npt

#: Euler-Mascheroni: the location of a Gumbel is its mean minus this many scales.
_EULER: Final = 0.5772156649015329
#: A year with fewer valid days than this has no maximum: its peak may be missing.
MIN_DAYS_PER_YEAR: Final = 330
#: Fewer complete years than this and a node has no return levels.
MIN_YEARS: Final = 20
#: The return periods GloFAS reports, in years.
RETURN_PERIODS: Final = (2, 5, 20)


def annual_maxima(
    by_day: Mapping[date, float], *, min_days: int = MIN_DAYS_PER_YEAR
) -> dict[int, float]:
    """The highest value of each calendar year with at least ``min_days`` values.

    ``by_day`` is one node of :func:`~glofas_ewds.glofas.discharge_by_day`.
    """
    years: dict[int, list[float]] = {}
    for day, value in by_day.items():
        if math.isfinite(value):
            years.setdefault(day.year, []).append(value)
    return {y: max(v) for y, v in sorted(years.items()) if len(v) >= min_days}


def gumbel_fit(maxima: npt.ArrayLike) -> tuple[float, float]:
    """Location and scale of a Gumbel, by L-moments (Hosking 1990).

    Needs at least two values.
    """
    x = np.sort(np.asarray(maxima, dtype=float))
    n = x.size
    if n < 2:
        raise ValueError("a Gumbel fit needs at least two maxima")
    b0 = float(x.mean())
    b1 = float((np.arange(n) / (n - 1) * x).mean())
    scale = (2 * b1 - b0) / math.log(2)
    return b0 - _EULER * scale, scale


def return_level(location: float, scale: float, years: float) -> float:
    """The flow exceeded on average once every ``years`` years."""
    if years <= 1:
        raise ValueError("a return period is longer than one year")
    return location - scale * math.log(-math.log(1 - 1 / years))


def return_levels(
    maxima: Iterable[float],
    *,
    periods: Sequence[float] = RETURN_PERIODS,
    min_years: int = MIN_YEARS,
) -> dict[float, float] | None:
    """``{period: level}`` from a node's annual maxima; ``None`` below ``min_years``
    or when the maxima do not vary (a dry cell)."""
    values = [v for v in maxima if math.isfinite(v)]
    if len(values) < max(min_years, 2):
        return None
    location, scale = gumbel_fit(values)
    if scale <= 0:
        return None
    return {p: return_level(location, scale, p) for p in periods}


__all__ = [
    "MIN_DAYS_PER_YEAR",
    "MIN_YEARS",
    "RETURN_PERIODS",
    "annual_maxima",
    "gumbel_fit",
    "return_level",
    "return_levels",
]
