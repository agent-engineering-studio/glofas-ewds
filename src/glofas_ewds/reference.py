"""A node's ordinary high flow, and how far a forecast is above it.

Pure: nothing here does I/O.

A forecast of 300 m³/s means nothing on its own: it is a flood on a torrent
and a dry summer on the Po. Dividing by the node's **own** reference, a high
percentile of its multi-year series, makes rivers comparable. Dividing by a
regional figure does not: 10 % of the Po is 186 m³/s, more than most rivers
ever carry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Final

#: Fewer days than this and a node has no reference: a percentile of a few
#: weeks says how wet those weeks were, not how big the river is.
MIN_REFERENCE_DAYS: Final = 365
#: How many days ahead a forecast peak is looked for, the day itself included.
PEAK_WINDOW_DAYS: Final = 7


def percentile(values: Sequence[float], p: float) -> float | None:
    """The ``p`` quantile (0-1) by linear interpolation; ``None`` for no values."""
    if not values:
        return None
    ordered = sorted(values)
    pos = p * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def references[K](
    series: Mapping[K, Sequence[float]],
    *,
    p: float = 0.9,
    min_days: int = MIN_REFERENCE_DAYS,
) -> dict[K, float | None]:
    """The ``p`` quantile of each series; ``None`` below ``min_days`` values."""
    return {k: percentile(v, p) if len(v) >= min_days else None for k, v in series.items()}


def discharge_ratio(peak: float | None, reference: float | None) -> float | None:
    """``peak / reference``; ``None`` when either is unknown or the reference is 0.

    ``None`` means "I don't know how big this river is", never "the river is low".
    """
    if peak is None or reference is None or reference <= 0:
        return None
    return peak / reference


def reference_before(
    by_day: Mapping[date, float],
    start: date,
    *,
    p: float = 0.9,
    min_days: int = MIN_REFERENCE_DAYS,
) -> float | None:
    """A node's reference from the days **before** ``start`` only.

    For a replay: a reference that contains the days being judged already
    knows about the event. ``None`` below ``min_days`` earlier days.
    """
    values = [v for day, v in by_day.items() if day < start]
    return percentile(values, p) if len(values) >= min_days else None


def peak_ratios(
    by_day: Mapping[date, float],
    reference: float | None,
    *,
    window_days: int = PEAK_WINDOW_DAYS,
) -> dict[date, float]:
    """For each day, the peak of the ``window_days`` from it over ``reference``.

    What a forecast issued that day would have given, replayed on a daily
    series: :func:`discharge_ratio` with the window slid by hand. Days missing
    from the window are skipped; an unknown or non-positive reference gives
    no ratios, never zeros.
    """
    if reference is None or reference <= 0:
        return {}
    out: dict[date, float] = {}
    for day in by_day:
        ahead = [by_day[d] for k in range(window_days) if (d := day + timedelta(days=k)) in by_day]
        if ahead:
            out[day] = max(ahead) / reference
    return out


__all__ = [
    "MIN_REFERENCE_DAYS",
    "PEAK_WINDOW_DAYS",
    "discharge_ratio",
    "peak_ratios",
    "percentile",
    "reference_before",
    "references",
]
