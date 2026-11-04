from __future__ import annotations

from datetime import date

from glofas_ewds import (
    GLOFAS_VERSION,
    ITALY,
    candidate_runs,
    fire_request,
    forecast_request,
    historical_request,
    months,
)


def test_months_cover_the_window_without_gaps() -> None:
    m = months(date(2024, 1, 30), date(2024, 3, 2))
    assert [(y, mo) for y, mo, _ in m] == [(2024, 1), (2024, 2), (2024, 3)]
    assert m[0][2] == ["30", "31"]
    assert len(m[1][2]) == 29  # leap year
    assert m[2][2] == ["01", "02"]


def test_history_is_glofas_4_over_italy() -> None:
    r = historical_request(2024, 5, ["16"])
    assert r["system_version"] == [GLOFAS_VERSION] == ["version_4_0"]
    assert r["product_type"] == ["consolidated"]
    assert r["variable"] == ["average_river_discharge_in_the_last_24_hours"]
    assert r["area"] == list(ITALY)
    assert historical_request(2024, 5, ["16"], product="intermediate")["product_type"] == [
        "intermediate"
    ]


def test_forecast_is_the_control_run_over_seven_days() -> None:
    r = forecast_request(date(2026, 10, 10))
    assert r["product_type"] == ["control_forecast"]
    assert r["day"] == ["10"]
    assert r["leadtime_hour"] == ["24", "48", "72", "96", "120", "144", "168"]
    assert forecast_request(date(2026, 10, 10), days=2, area=(1, 2, 3, 4))["area"] == [1, 2, 3, 4]


def test_fire_request_asks_six_components_at_a_quarter_degree() -> None:
    r = fire_request(2025, 7, ["01", "02"])
    assert len(r["variable"]) == 6
    assert r["grid"] == "0.25/0.25"
    assert r["dataset_type"] == "consolidated_dataset"


def test_candidate_runs_skip_what_you_have() -> None:
    today = date(2026, 10, 10)
    assert candidate_runs(today) == [today, date(2026, 10, 9)]
    assert candidate_runs(today, latest_saved=date(2026, 10, 9)) == [today]
    assert candidate_runs(today, latest_saved=today) == []
