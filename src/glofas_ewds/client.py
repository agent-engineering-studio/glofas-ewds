"""An async front for the EWDS downloads, for code that runs in an event loop.

The EWDS is a queue: a request waits minutes before its file is ready, and
``cdsapi`` blocks while it waits. :class:`EwdsClient` runs each download in a
thread so your loop keeps serving.

Credentials: pass ``url`` and ``key``, or leave them out and ``cdsapi`` reads
``CDSAPI_URL`` / ``CDSAPI_KEY`` or ``~/.cdsapirc``. Accept each dataset's
licence once on its page on the EWDS, or every request answers 403.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

from glofas_ewds.download import (
    Retriever,
    download_ensemble,
    download_fire,
    download_forecast,
    download_history,
)
from glofas_ewds.errors import GlofasEwdsError
from glofas_ewds.request import ITALY, Area, candidate_runs

#: The EWDS API, for ``url``.
EWDS_URL = "https://ewds.climate.copernicus.eu/api"


def cdsapi_client(url: str | None = None, key: str | None = None) -> Retriever:
    """A quiet ``cdsapi.Client`` (needs the ``ewds`` extra)."""
    try:
        import cdsapi
    except ImportError as exc:
        raise GlofasEwdsError("downloading needs cdsapi: pip install 'glofas-ewds[ewds]'") from exc
    client: Retriever = cdsapi.Client(url=url, key=key, quiet=True, progress=False)
    return client


class EwdsClient:
    """GloFAS history and forecast, and the Copernicus FWI, downloaded off the event loop."""

    def __init__(
        self,
        folder: Path | str,
        *,
        url: str | None = None,
        key: str | None = None,
        retriever: Retriever | None = None,
        area: Area = ITALY,
    ) -> None:
        self.folder = Path(folder)
        self.area = area
        self._url, self._key = url, key
        self._retriever = retriever

    @property
    def retriever(self) -> Retriever:
        """The object that sends the requests; a ``cdsapi.Client`` unless you gave one."""
        if self._retriever is None:
            self._retriever = cdsapi_client(self._url, self._key)
        return self._retriever

    async def history(self, start: date, end: date) -> list[Path]:
        """Daily discharge files from ``start`` to ``end``; see :func:`download_history`."""
        return await asyncio.to_thread(
            download_history,
            self.folder / "history",
            start,
            end,
            client=self.retriever,
            area=self.area,
        )

    async def forecast(self, run: date) -> Path:
        """The control forecast file of ``run``; see :func:`download_forecast`."""
        return await asyncio.to_thread(
            download_forecast, self.folder / "forecast", run, client=self.retriever, area=self.area
        )

    async def ensemble(self, run: date) -> Path:
        """The perturbed members of ``run``; see :func:`download_ensemble`."""
        return await asyncio.to_thread(
            download_ensemble, self.folder / "ensemble", run, client=self.retriever, area=self.area
        )

    async def latest_forecast(
        self, *, today: date | None = None, latest_saved: date | None = None
    ) -> tuple[date, Path] | None:
        """The newest run you do not have yet: today's, or yesterday's if today's
        is not published.

        ``None`` when you already have the newest. Raises :class:`GlofasEwdsError`
        when no candidate run could be downloaded.
        """
        runs = candidate_runs(today or datetime.now(UTC).date(), latest_saved=latest_saved)
        last: Exception | None = None
        for run in runs:
            try:
                return run, await self.forecast(run)
            except Exception as exc:
                last = exc
        if last is not None:
            raise GlofasEwdsError(f"no GloFAS run among {runs}: {last}") from last
        return None

    async def fire(self, start: date, end: date) -> list[Path]:
        """Copernicus FWI files from ``start`` to ``end``; see :func:`download_fire`."""
        return await asyncio.to_thread(
            download_fire, self.folder / "fwi", start, end, client=self.retriever, area=self.area
        )


__all__ = ["EWDS_URL", "EwdsClient", "cdsapi_client"]
