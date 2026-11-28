"""How likely a forecast peak is: the share of ensemble members above a threshold.

Pure: nothing here does I/O.

The control run says one future; the 50 perturbed members of the same run
say how sure it is. Three members over the river's ordinary high flow and
forty over it are the same control forecast and very different news. The
threshold is yours: a node's own reference
(:func:`~glofas_ewds.reference.references`) or a return level
(:func:`~glofas_ewds.return_period.return_levels`), never a regional figure.

A member that is all NaN (masked) does not vote. With no member left, or no
threshold, the answer is ``None``: "I don't know", never "0 %".
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import numpy.typing as npt


def _valid(
    members: npt.ArrayLike, threshold: float | None
) -> tuple[npt.NDArray[np.float64], float] | None:
    """The members that vote, and the threshold; ``None`` when there is no answer."""
    if threshold is None or threshold <= 0:
        return None
    a = np.atleast_2d(np.asarray(members, dtype=float))
    a = a[np.isfinite(a).any(axis=1)]
    return (a, threshold) if a.size else None


def exceedance_probability(members: npt.ArrayLike, threshold: float | None) -> float | None:
    """Share (0-1) of members whose peak over the lead times reaches ``threshold``.

    ``members`` is (member, lead time), as
    :func:`~glofas_ewds.glofas.ensemble_members` gives it.
    """
    valid = _valid(members, threshold)
    if valid is None:
        return None
    a, t = valid
    return float((np.nanmax(a, axis=1) >= t).mean())


def exceedance_by_lead(members: npt.ArrayLike, threshold: float | None) -> list[float] | None:
    """For each lead time, the share of members at or above ``threshold``.

    Says *when*: ``[0.0, 0.1, 0.6, 0.4, ...]`` is a peak most likely on day 3.
    A lead time where every member is masked gives NaN.
    """
    valid = _valid(members, threshold)
    if valid is None:
        return None
    a, t = valid
    finite = np.isfinite(a)
    voters = finite.sum(axis=0)
    over = (np.where(finite, a, -np.inf) >= t).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return [float(x) for x in np.where(voters > 0, over / np.maximum(voters, 1), np.nan)]


def peak_day(members: npt.ArrayLike, run: date) -> date | None:
    """The day of the highest value of a (member, lead time) forecast of ``run``.

    The k-th lead time (``leadtime_hour`` 24·(k+1)) is the mean of the day
    ``run + k``: the GloFAS ``valid_time`` is the end of the day. A single
    series (lead time only) is one member. ``None`` when everything is masked.
    """
    a = np.atleast_2d(np.asarray(members, dtype=float))
    by_lead = np.max(np.where(np.isfinite(a), a, -np.inf), axis=0)
    if not np.isfinite(by_lead).any():
        return None
    return run + timedelta(days=int(np.argmax(by_lead)))


__all__ = ["exceedance_by_lead", "exceedance_probability", "peak_day"]
