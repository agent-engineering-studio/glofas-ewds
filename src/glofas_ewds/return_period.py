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
from dataclasses import dataclass
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
#: How far a run's saved peak may be from the peak behind the ratio, as a share
#: of the larger of the two, for the run's peak day to be that peak's day.
PEAK_TOLERANCE: Final = 0.01


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


@dataclass(frozen=True, slots=True)
class FloodLabel:
    """A forecast peak said in return periods: "above the 5-year flood"."""

    #: The longest return period reached (2, 5 or 20 years); ``None`` when the
    #: peak is below the 2-year flood.
    years: int | None
    #: The forecast peak, in m³/s.
    peak: float
    #: The thresholds that were known, ``{years: m³/s}``.
    thresholds: dict[int, float]
    #: The day of the peak in the run, when the run is the one behind the ratio.
    day: date | None = None


def flood_label(
    ratio: float | None,
    reference: float | None,
    thresholds: Mapping[int, float | None],
    forecast: tuple[float, date | None] | None = None,
    *,
    tolerance: float = PEAK_TOLERANCE,
) -> FloodLabel | None:
    """The forecast peak as a return-period label; ``None`` when a piece is missing.

    The peak is recovered exactly as ``ratio * reference``
    (:func:`~glofas_ewds.reference.discharge_ratio` undone) and compared with
    ``thresholds``, ``{years: m³/s}`` for the same cell: the official ones
    (:func:`~glofas_ewds.thresholds.flood_thresholds`) or your own
    (:func:`return_levels`). Unknown or non-positive thresholds are ignored.
    Without a reference or without the 2-year threshold there is no label:
    "I don't know" is not "below the flood".

    ``forecast`` is ``(peak, day)`` of a saved run. Its day is kept only when
    its peak is within ``tolerance`` of the recovered one: further apart, the
    ratio came from another run and the day belongs to another forecast.
    """
    if ratio is None or reference is None or reference <= 0:
        return None
    known = {years: t for years, t in thresholds.items() if t is not None and t > 0}
    if RETURN_PERIODS[0] not in known:
        return None
    peak = ratio * reference
    reached = [years for years, t in known.items() if peak >= t]
    day = None
    if forecast is not None and forecast[1] is not None:
        saved = forecast[0]
        if abs(saved - peak) <= tolerance * max(saved, peak, 1.0):
            day = forecast[1]
    return FloodLabel(years=max(reached) if reached else None, peak=peak, thresholds=known, day=day)


__all__ = [
    "MIN_DAYS_PER_YEAR",
    "MIN_YEARS",
    "PEAK_TOLERANCE",
    "RETURN_PERIODS",
    "FloodLabel",
    "annual_maxima",
    "flood_label",
    "gumbel_fit",
    "return_level",
    "return_levels",
]
