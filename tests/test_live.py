"""Contract tests against the live EWDS and Open-Meteo, weekly in CI (``live.yml``).

Every trap in the README was measured once, on a date: the cell one step
east (11 October 2026, 28 nodes), the latency of the history, the "valid
combination" answer for a month not consolidated yet, the shape of the
forecast file, the GRIB names of the FWI. None of them is promised by
Copernicus or Open-Meteo, and the synthetic files of the other tests cannot
notice when one moves. These tests ask the real services again. Each failure
message says which fact moved and what to change.

They are skipped unless ``GLOFAS_EWDS_LIVE=1``; then they need ``CDSAPI_KEY``
(an EWDS key, the licences of ``cems-glofas-historical``,
``cems-glofas-forecast`` and ``cems-fire-historical-v1`` accepted) and fail,
not skip, without it:

    GLOFAS_EWDS_LIVE=1 CDSAPI_KEY=... uv run pytest -m live --no-cov -v

About six EWDS requests, each a day of Italy (a few hundred kB), plus one
Open-Meteo call. The EWDS queue makes the run take minutes, not seconds.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from glofas_ewds import (
    EWDS_URL,
    FIRE_VARIABLES,
    GRID_STEP,
    HISTORY_LATENCY_DAYS,
    EwdsClient,
    Node,
    Retriever,
    cdsapi_client,
    declared_cell,
    discharge_series,
    download_fire,
    download_history,
    fire_values,
    forecast_peaks,
    open_meteo_cell,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("GLOFAS_EWDS_LIVE") != "1", reason="set GLOFAS_EWDS_LIVE=1"),
]

#: Toce, Lamone, Arno (the README's rivers) and five of Limen's measured nodes.
NODES: list[Node] = [
    (8.43, 45.97),
    (11.88, 44.29),
    (11.25, 43.77),
    (11.9, 44.3),
    (12.0, 44.2),
    (16.6, 40.7),
    (7.7, 45.1),
    (15.6, 38.1),
]
#: Days Open-Meteo still serves as ``consolidated_v4``: in November 2026 that
#: model ended in 2024, and after it Open-Meteo's history is the archive of its
#: forecasts, which is not the reanalysis. Same model on both sides, or the
#: comparison measures the model and not the cell.
CONSOLIDATED_DAYS = (date(2024, 3, 1), date(2024, 3, 3))
OPEN_METEO_FLOOD = "https://flood-api.open-meteo.com/v1/flood"


class Recorder:
    """Forwards to cdsapi and keeps what was asked, to see the fallbacks."""

    def __init__(self, client: Retriever) -> None:
        self.client = client
        self.asked: list[tuple[str, dict[str, Any]]] = []

    def retrieve(self, name: str, request: dict[str, Any], target: str) -> Any:
        self.asked.append((name, request))
        return self.client.retrieve(name, request, target)


@pytest.fixture(scope="module")
def client() -> Recorder:
    key = os.environ.get("CDSAPI_KEY")
    if not key:
        pytest.fail("GLOFAS_EWDS_LIVE=1 needs CDSAPI_KEY (an EWDS key): a live run without it")
    return Recorder(cdsapi_client(os.environ.get("CDSAPI_URL", EWDS_URL), key))


@pytest.fixture(scope="module")
def folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("ewds")


def open_meteo(nodes: list[Node], start: date, end: date, model: str) -> list[list[float | None]]:
    query = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(lat) for _, lat in nodes),
            "longitude": ",".join(str(lon) for lon, _ in nodes),
            "daily": "river_discharge",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "models": model,
        }
    )
    with urllib.request.urlopen(f"{OPEN_METEO_FLOOD}?{query}", timeout=60) as answer:
        body = json.load(answer)
    return [loc["daily"]["river_discharge"] for loc in body]


def neighbours(cell: Node) -> list[Node]:
    lon, lat = cell
    return [
        (round(lon + dx * GRID_STEP, 3), round(lat + dy * GRID_STEP, 3))
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    ]


def test_open_meteo_serves_the_cell_one_step_east(client: Recorder, folder: Path) -> None:
    start, end = CONSOLIDATED_DAYS
    files = download_history(folder / "history", start, end, client=client)
    theirs = open_meteo(NODES, start, end, "consolidated_v4")
    wrong: dict[Node, Node] = {}
    for node, values in zip(NODES, theirs, strict=True):
        assert all(v is not None for v in values), (
            f"Open-Meteo has no consolidated_v4 at {node} for {start}..{end}: move "
            "CONSOLIDATED_DAYS to days it still serves"
        )
        target = np.array(values, dtype=float)
        # Read every cell of the 3x3 around the declared one as if it were a node:
        # discharge_series reads open_meteo_cell(node), so ask for the node one step west.
        around = neighbours(declared_cell(*node))
        as_nodes = [(round(lon - GRID_STEP, 3), lat) for lon, lat in around]
        assert [open_meteo_cell(*n) for n in as_nodes] == around
        series = discharge_series(files, as_nodes, start=start, end=end)
        errors = {
            cell: float(np.abs(np.array(series[n]) - target).max()) if series[n] else np.inf
            for cell, n in zip(around, as_nodes, strict=True)
        }
        # Ties (two dry cells, both ~0) are not a wrong cell: the served one
        # must be among the closest, not first among them.
        closest = min(errors.values())
        if errors[open_meteo_cell(*node)] > closest + 0.01:
            wrong[node] = min(errors, key=errors.__getitem__)
    assert not wrong, (
        "the EWDS cell closest to Open-Meteo's numbers is no longer open_meteo_cell for "
        f"{len(wrong)} of {len(NODES)} nodes ({wrong}); declared cells: "
        f"{ {n: declared_cell(*n) for n in wrong} }. If they are the declared cells, "
        "Open-Meteo fixed its shift: drop the step east in cells.open_meteo_cell"
    )


def test_open_meteo_and_the_ewds_give_the_same_numbers(client: Recorder, folder: Path) -> None:
    start, end = CONSOLIDATED_DAYS
    files = download_history(folder / "history", start, end, client=client)
    ours = discharge_series(files, NODES, start=start, end=end)
    theirs = open_meteo(NODES, start, end, "consolidated_v4")
    for node, values in zip(NODES, theirs, strict=True):
        # Open-Meteo rounds to two decimals and stores float16-ish: 2 % or 0.05 m³/s.
        assert ours[node] == pytest.approx(values, rel=0.02, abs=0.05), (
            f"{node}: EWDS {ours[node]} against Open-Meteo {values}. Same cell, different "
            "numbers: a model version changed on one side (GLOFAS_VERSION is version_4_0)"
        )


def test_the_history_reaches_the_latency_and_recent_days_are_intermediate(
    client: Recorder, folder: Path
) -> None:
    day = datetime.now(UTC).date() - timedelta(days=HISTORY_LATENCY_DAYS)
    before = len(client.asked)
    try:
        files = download_history(folder / "recent", day, day, client=client)
    except Exception as exc:
        pytest.fail(
            f"no history for {day} ({exc}): the EWDS is later than HISTORY_LATENCY_DAYS "
            f"= {HISTORY_LATENCY_DAYS}, or a not-yet-consolidated month no longer answers "
            "'valid combination' (download._no_combination)"
        )
    products = [r["product_type"][0] for _, r in client.asked[before:]]
    assert products == ["consolidated", "intermediate"], (
        f"asked {products} for {day}: if the consolidated history now reaches this "
        "day, the fallback is unused, not wrong; update the README's dates"
    )
    series = discharge_series(files, NODES, start=day, end=day)
    assert any(series.values()), f"the {day} file holds no value on any node"


async def test_the_latest_forecast_is_a_control_run_of_seven_days(
    client: Recorder, folder: Path
) -> None:
    ewds = EwdsClient(folder, retriever=client)
    latest = await ewds.latest_forecast()
    assert latest is not None
    run, path = latest
    assert run >= datetime.now(UTC).date() - timedelta(days=1)
    netcdf4 = pytest.importorskip("netCDF4")
    with netcdf4.Dataset(path) as ds:
        dis = ds.variables["dis24"]
        assert dis.ndim == 4, f"dis24 has dims {dis.dimensions}: forecast_peaks expects 4"
        assert dis.shape[0] == 7 and dis.shape[1] == 1, (
            f"dis24 is {dis.shape}: forecast_peaks reads (lead time, run, lat, lon)"
        )
    peaks = forecast_peaks(path, NODES)
    assert len(peaks) >= len(NODES) // 2, f"peaks for only {sorted(peaks)}"


def test_the_fire_file_still_names_every_component(client: Recorder, folder: Path) -> None:
    day = date(2025, 7, 15)
    files = download_fire(folder / "fwi", day, day, client=client)
    fire_nodes: list[Node] = [(11.25, 43.75), (16.5, 40.75), (9.0, 39.25)]
    values = fire_values(files, fire_nodes)
    assert values, "no FWI on any node: did the variable dimensions change?"
    found: set[str] = set()
    for components in values.values():
        found |= components.keys()
    assert found == set(FIRE_VARIABLES), (
        f"missing {set(FIRE_VARIABLES) - found}: a long_name in the file changed "
        "(fwi.FIRE_VARIABLES matches them by their start)"
    )
