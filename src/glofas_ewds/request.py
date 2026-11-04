"""The EWDS requests for GloFAS, built without sending them.

Pure: nothing here does I/O. Each function returns the dict you pass to
``cdsapi.Client.retrieve(dataset, request, target)``.

Three choices matter more than they look:

* **GloFAS 4, not 5.** Open-Meteo serves its forecast from GloFAS 4
  (checked on 11 October 2026 at Faenza: 7.1 / 6.1 / 8.9 m³/s from the EWDS
  against 7.3 / 5.9 / 8.9 from Open-Meteo), and version 5 gives about half.
  A ratio of a v4 forecast to a v5 reference is a number without meaning.
* **Consolidated, then intermediate.** The consolidated history arrives
  months late; the recent months exist only as ``intermediate``, the same
  model and version. :func:`historical_request` takes the product.
* **The control run.** The forecast dataset holds an ensemble; the control
  run is the one Open-Meteo serves as ``forecast_v4``. The 50 perturbed
  members (:data:`ENSEMBLE`) say how likely a peak is, which one run cannot.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Final

#: The history: reanalysis-driven discharge, one value per day.
HISTORICAL_DATASET: Final = "cems-glofas-historical"
#: The daily forecast (00 UTC run).
FORECAST_DATASET: Final = "cems-glofas-forecast"
#: The model version Open-Meteo uses for its forecast.
GLOFAS_VERSION: Final = "version_4_0"
#: How many days back the EWDS history reaches (intermediate included).
#: Measured on 11 October 2026: consolidated to June, intermediate to 8 October.
HISTORY_LATENCY_DAYS: Final = 4
#: Days of forecast to ask for, one value per 24 hours of lead time.
FORECAST_DAYS: Final = 7
#: The ``product_type`` of the single control run, and of the perturbed members.
CONTROL: Final = "control_forecast"
ENSEMBLE: Final = "ensemble_perturbed_forecasts"

#: North, west, south, east in degrees, the order the EWDS wants.
Area = tuple[float, float, float, float]

#: Italy with half a degree of margin.
ITALY: Final[Area] = (47.6, 6.0, 35.0, 19.0)

#: The variable names inside the NetCDF files.
HISTORICAL_VARIABLE: Final = "avg_dis"
FORECAST_VARIABLE: Final = "dis24"


def months(start: date, end: date) -> list[tuple[int, int, list[str]]]:
    """``(year, month, days)`` for every month between ``start`` and ``end``, both included.

    The EWDS limits how much one request may hold; a month of Italy is well
    inside it, and a month is what you re-download when one fails.
    """
    out: list[tuple[int, int, list[str]]] = []
    day = start
    while day <= end:
        year, month = day.year, day.month
        days: list[str] = []
        while day <= end and day.month == month:
            days.append(f"{day.day:02d}")
            day += timedelta(days=1)
        out.append((year, month, days))
    return out


def historical_request(
    year: int,
    month: int,
    days: list[str],
    *,
    product: str = "consolidated",
    area: Area = ITALY,
    version: str = GLOFAS_VERSION,
) -> dict[str, Any]:
    """Daily mean discharge for ``days`` of one month; ``product`` is
    ``consolidated`` or ``intermediate``."""
    return {
        "system_version": [version],
        "hydrological_model": ["lisflood"],
        "product_type": [product],
        "variable": ["average_river_discharge_in_the_last_24_hours"],
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": days,
        "timespan": ["time_mean"],
        "area": list(area),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def forecast_request(
    run: date, *, days: int = FORECAST_DAYS, area: Area = ITALY, product: str = CONTROL
) -> dict[str, Any]:
    """The run of ``run`` (00 UTC), one step per 24 hours of lead time.

    ``product`` is :data:`CONTROL` (one run, what Open-Meteo serves) or
    :data:`ENSEMBLE` (the 50 perturbed members: about 50 times the size).
    """
    return {
        "system_version": ["operational"],
        "hydrological_model": ["lisflood"],
        "product_type": [product],
        "variable": ["river_discharge_in_the_last_24_hours"],
        "year": [str(run.year)],
        "month": [f"{run.month:02d}"],
        "day": [f"{run.day:02d}"],
        "leadtime_hour": [str(24 * d) for d in range(1, days + 1)],
        "area": list(area),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def candidate_runs(today: date, *, latest_saved: date | None = None) -> list[date]:
    """The forecast runs worth trying, newest first.

    GloFAS runs once a day at 00 UTC and the EWDS publishes it some hours
    later: early in the day today's run is usually missing, so yesterday's is
    the fallback. Runs you already have are left out.
    """
    return [
        r for r in (today, today - timedelta(days=1)) if latest_saved is None or r > latest_saved
    ]


__all__ = [
    "CONTROL",
    "ENSEMBLE",
    "FORECAST_DATASET",
    "FORECAST_DAYS",
    "FORECAST_VARIABLE",
    "GLOFAS_VERSION",
    "HISTORICAL_DATASET",
    "HISTORICAL_VARIABLE",
    "HISTORY_LATENCY_DAYS",
    "ITALY",
    "Area",
    "candidate_runs",
    "forecast_request",
    "historical_request",
    "months",
]
