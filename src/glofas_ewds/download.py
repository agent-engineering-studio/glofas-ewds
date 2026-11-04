"""Download EWDS files to a folder, one month (or one run) per file.

Synchronous, like ``cdsapi``: from async code call these in a thread, or use
:class:`~glofas_ewds.client.EwdsClient`. They work with any object that has
``retrieve(dataset, request, target)``, so you can pass a ``cdsapi.Client``,
your own wrapper (a budget, a queue timeout) or a fake in tests.

Every function can be run again: a file already there is not requested.
Each download goes to ``<name>.part`` and is renamed when complete, so a
request you stopped waiting for never leaves half a file that passes for a
whole one.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from glofas_ewds.fwi import FIRE_DATASET, FIRE_VERSION, fire_request
from glofas_ewds.request import (
    FORECAST_DATASET,
    GLOFAS_VERSION,
    HISTORICAL_DATASET,
    ITALY,
    Area,
    forecast_request,
    historical_request,
    months,
)


class Retriever(Protocol):
    """What ``cdsapi.Client`` offers and these functions use."""

    def retrieve(self, name: str, request: dict[str, Any], target: str) -> Any: ...


def _no_combination(exc: Exception) -> bool:
    # What the EWDS answers when a month has no consolidated data yet.
    return "valid combination" in str(exc)


def _area_tag(area: Area) -> str:
    return "" if area == ITALY else "_" + "_".join(f"{v:g}" for v in area)


def _fetch(client: Retriever, dataset: str, request: dict[str, Any], target: Path) -> None:
    part = target.with_suffix(".part")
    client.retrieve(dataset, request, str(part))
    part.rename(target)


def _monthly(
    folder: Path,
    start: date,
    end: date,
    *,
    client: Retriever,
    dataset: str,
    prefix: str,
    build: Callable[..., dict[str, Any]],
    fallback: str,
    area: Area,
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for year, month, days in months(start, end):
        # The days are in the name: the month at the edge of the window grows
        # every day, and yesterday's partial month must not pass for today's.
        target = folder / f"{prefix}_{year}{month:02d}_{days[0]}-{days[-1]}{_area_tag(area)}.nc"
        if not target.exists():
            try:
                _fetch(client, dataset, build(year, month, days, area=area), target)
            except Exception as exc:
                if not _no_combination(exc):
                    raise
                _fetch(
                    client, dataset, build(year, month, days, product=fallback, area=area), target
                )
        files.append(target)
    return files


def download_history(
    folder: Path, start: date, end: date, *, client: Retriever, area: Area = ITALY
) -> list[Path]:
    """GloFAS 4 daily discharge, one NetCDF per month; intermediate where the
    consolidated history does not reach yet."""
    return _monthly(
        folder,
        start,
        end,
        client=client,
        dataset=HISTORICAL_DATASET,
        prefix=f"glofas_{GLOFAS_VERSION}",
        build=historical_request,
        fallback="intermediate",
        area=area,
    )


def download_forecast(folder: Path, run: date, *, client: Retriever, area: Area = ITALY) -> Path:
    """The control forecast of ``run``, one NetCDF."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"glofas_forecast_{run.isoformat()}{_area_tag(area)}.nc"
    if not target.exists():
        _fetch(client, FORECAST_DATASET, forecast_request(run, area=area), target)
    return target


def download_fire(
    folder: Path, start: date, end: date, *, client: Retriever, area: Area = ITALY
) -> list[Path]:
    """The Copernicus FWI components, one NetCDF per month."""
    return _monthly(
        folder,
        start,
        end,
        client=client,
        dataset=FIRE_DATASET,
        prefix=f"cems_fire_{FIRE_VERSION}",
        build=fire_request,
        fallback="intermediate_dataset",
        area=area,
    )


__all__ = ["Retriever", "download_fire", "download_forecast", "download_history"]
