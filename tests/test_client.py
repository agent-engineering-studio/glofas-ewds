from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeRetriever

import glofas_ewds
from glofas_ewds import EwdsClient, GlofasEwdsError, cdsapi_client


async def test_downloads_go_to_one_folder_per_kind(
    tmp_path: Path, retriever: FakeRetriever
) -> None:
    ewds = EwdsClient(tmp_path, retriever=retriever)
    history = await ewds.history(date(2024, 5, 1), date(2024, 5, 2))
    forecast = await ewds.forecast(date(2026, 10, 10))
    fire = await ewds.fire(date(2025, 7, 1), date(2025, 7, 1))
    assert history[0].parent == tmp_path / "history"
    assert forecast.parent == tmp_path / "forecast"
    assert fire[0].parent == tmp_path / "fwi"


async def test_latest_forecast_falls_back_to_yesterday(tmp_path: Path) -> None:
    r = FakeRetriever(lambda req: RuntimeError("not yet") if req["day"] == ["10"] else None)
    run, path = await EwdsClient(tmp_path, retriever=r).latest_forecast(
        today=date(2026, 10, 10)
    ) or (
        None,
        None,
    )
    assert run == date(2026, 10, 9)
    assert path is not None and path.exists()


async def test_latest_forecast_has_nothing_new(tmp_path: Path, retriever: FakeRetriever) -> None:
    ewds = EwdsClient(tmp_path, retriever=retriever)
    today = date(2026, 10, 10)
    assert await ewds.latest_forecast(today=today, latest_saved=today) is None
    assert retriever.calls == []


async def test_latest_forecast_raises_when_no_run_comes(tmp_path: Path) -> None:
    r = FakeRetriever(lambda _r: RuntimeError("queue down"))
    with pytest.raises(GlofasEwdsError, match="queue down"):
        await EwdsClient(tmp_path, retriever=r).latest_forecast(today=date(2026, 10, 10))


def test_the_default_retriever_is_a_quiet_cdsapi_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[dict[str, Any]] = []

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            made.append(kwargs)

    fake = types.ModuleType("cdsapi")
    fake.Client = Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cdsapi", fake)
    ewds = EwdsClient(tmp_path, url=glofas_ewds.EWDS_URL, key="k")
    assert ewds.retriever is ewds.retriever
    assert made == [{"url": glofas_ewds.EWDS_URL, "key": "k", "quiet": True, "progress": False}]


def test_without_cdsapi_the_error_says_which_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "cdsapi", None)
    with pytest.raises(GlofasEwdsError, match=r"glofas-ewds\[ewds\]"):
        cdsapi_client()


def test_importing_the_package_needs_only_numpy() -> None:
    import subprocess

    code = "import sys, glofas_ewds; assert not {'netCDF4', 'cdsapi'} & set(sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True)
