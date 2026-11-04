from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeRetriever

from glofas_ewds import download_fire, download_forecast, download_history


def test_history_does_not_ask_twice_for_a_month(tmp_path: Path, retriever: FakeRetriever) -> None:
    download_history(tmp_path, date(2024, 4, 29), date(2024, 5, 2), client=retriever)
    files = download_history(tmp_path, date(2024, 4, 29), date(2024, 5, 2), client=retriever)
    assert [r["month"][0] for _, r in retriever.calls] == ["04", "05"]
    assert [f.name for f in files] == [
        "glofas_version_4_0_202404_29-30.nc",
        "glofas_version_4_0_202405_01-02.nc",
    ]
    assert not list(tmp_path.glob("*.part"))


def test_another_area_gets_its_own_files(tmp_path: Path, retriever: FakeRetriever) -> None:
    files = download_history(
        tmp_path, date(2024, 5, 1), date(2024, 5, 1), client=retriever, area=(46.0, 8.0, 45.5, 8.5)
    )
    assert files[0].name == "glofas_version_4_0_202405_01-01_46_8_45.5_8.5.nc"
    assert retriever.calls[0][1]["area"] == [46.0, 8.0, 45.5, 8.5]


def _no_consolidated(request: dict[str, Any]) -> Exception | None:
    if request.get("product_type") == ["consolidated"] or (
        request.get("dataset_type") == "consolidated_dataset"
    ):
        return RuntimeError("Request has not produced a valid combination of values")
    return None


def test_a_month_without_consolidated_data_takes_intermediate(tmp_path: Path) -> None:
    r = FakeRetriever(_no_consolidated)
    download_history(tmp_path, date(2026, 7, 1), date(2026, 7, 3), client=r)
    assert [c[1]["product_type"][0] for c in r.calls] == ["consolidated", "intermediate"]
    assert len(list(tmp_path.glob("*.nc"))) == 1


def test_another_error_is_not_turned_into_intermediate(tmp_path: Path) -> None:
    r = FakeRetriever(lambda _r: RuntimeError("403 required licences not accepted"))
    with pytest.raises(RuntimeError, match="licences"):
        download_history(tmp_path, date(2026, 7, 1), date(2026, 7, 3), client=r)
    assert not list(tmp_path.iterdir())


def test_a_forecast_run_is_downloaded_once(tmp_path: Path, retriever: FakeRetriever) -> None:
    a = download_forecast(tmp_path, date(2026, 10, 10), client=retriever)
    b = download_forecast(tmp_path, date(2026, 10, 10), client=retriever)
    assert a == b == tmp_path / "glofas_forecast_2026-10-10.nc"
    assert [c[1]["day"] for c in retriever.calls] == [["10"]]


def test_fire_falls_back_to_the_intermediate_dataset(tmp_path: Path) -> None:
    r = FakeRetriever(_no_consolidated)
    files = download_fire(tmp_path, date(2026, 10, 1), date(2026, 10, 2), client=r)
    assert [c[1]["dataset_type"] for c in r.calls] == [
        "consolidated_dataset",
        "intermediate_dataset",
    ]
    assert files[0].name == "cems_fire_4_1_202610_01-02.nc"
