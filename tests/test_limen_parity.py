"""Parity with Limen: the functions that moved here give Limen's numbers.

The ``_limen_*`` functions are Limen's implementations, copied as they stood
when the logic moved (``core/piena.py``, ``integrations/openmeteo/flood.py``,
``cli/backtest_flood.py``, ``integrations/copernicus/ewds_glofas.py`` and
``glofas_soglie.py``): the library does not import Limen. Each test runs both
on the same fixed inputs.
"""

from __future__ import annotations

import itertools
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np
import pytest
from conftest import LATS, LONS, write_cube

from glofas_ewds import (
    FloodLabel,
    cell_indices,
    discharge_ratio,
    flood_label,
    flood_thresholds,
    forecast_peak_days,
    open_meteo_cell,
    peak_day,
    peak_ratios,
    percentile,
    read_threshold,
    reference_before,
    references,
    threshold_file_name,
    threshold_url,
)

# --- Limen, verbatim -------------------------------------------------------


def _limen_piena(
    rapporto: float | None,
    q90: float | None,
    soglie: dict[int, float | None],
    previsto: tuple[float, date | None] | None = None,
) -> tuple[int | None, float, dict[int, float], date | None] | None:
    """``core.piena.piena``; the ``Piena`` fields as a tuple."""
    if rapporto is None or q90 is None or q90 <= 0:
        return None
    note = {anni: s for anni, s in soglie.items() if s is not None and s > 0}
    if 2 not in note:
        return None
    picco = rapporto * q90
    superati = [anni for anni, s in note.items() if picco >= s]
    giorno = None
    if previsto is not None and previsto[1] is not None:
        salvato = previsto[0]
        if abs(salvato - picco) <= 0.01 * max(salvato, picco, 1.0):
            giorno = previsto[1]
    return (max(superati) if superati else None, picco, note, giorno)


def _limen_percentile_of(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = p * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _limen_discharge_ratios(daily: dict[date, float], reference: float) -> dict[date, float]:
    if reference <= 0.0:
        return {}
    out: dict[date, float] = {}
    for day in daily:
        future = [
            daily[day + timedelta(days=k)] for k in range(0, 7) if day + timedelta(days=k) in daily
        ]
        if not future:
            continue
        out[day] = max(future) / reference
    return out


def _limen_node_reference(
    daily: dict[date, float], *, percentile: float, min_days: int
) -> float | None:
    values = [daily[day] for day in sorted(daily)]
    if len(values) < min_days:
        return None
    return _limen_percentile_of(values, percentile)


def _limen_giorno_del_picco(valori: Any, corsa: date) -> date | None:
    serie = np.asarray(valori, dtype=float)
    if serie.ndim == 1:
        serie = serie[None]
    per_giorno = np.nanmax(np.where(np.isfinite(serie), serie, -np.inf), axis=0)
    if not np.isfinite(per_giorno).any():
        return None
    return corsa + timedelta(days=int(np.argmax(per_giorno)))


def _limen_leggi(path: Path, nodi: list[tuple[float, float]]) -> list[float | None]:
    if not nodi:
        return []
    with netCDF4.Dataset(path) as ds:
        variabili = ds.variables
        nomi = [k for k, v in variabili.items() if v.ndim == 2]
        if len(nomi) != 1:
            raise ValueError(f"attesa una variabile 2-D, trovate {nomi}")
        lat = next(v for k, v in variabili.items() if k.lower().startswith("lat"))
        lon = next(v for k, v in variabili.items() if k.lower().startswith("lon"))
        var = variabili[nomi[0]]
        lats = np.asarray(lat[:], dtype=float)
        lons = np.asarray(lon[:], dtype=float)
        celle = [open_meteo_cell(x, y) for x, y in nodi]
        righe, colonne, dentro = cell_indices(lats, lons, celle)
        r0, r1 = int(righe.min()), int(righe.max()) + 1
        c0, c1 = int(colonne.min()), int(colonne.max()) + 1
        blocco = np.ma.filled(np.ma.asarray(var[r0:r1, c0:c1], dtype=float), np.nan)
    out: list[float | None] = []
    for r, c, ok in zip(righe, colonne, dentro, strict=True):
        v = float(blocco[r - r0, c - c0]) if ok else float("nan")
        out.append(v if np.isfinite(v) and v > 0 else None)
    return out


# --- fixed inputs ----------------------------------------------------------

D0 = date(2024, 1, 1)


def _series(n: int, *, seed: int, gaps: bool = False) -> dict[date, float]:
    """A deterministic daily "river": a seasonal wave, noise and a few floods."""
    rng = np.random.default_rng(seed)
    flow = 40 + 25 * np.sin(np.arange(n) / 58.0) + rng.gamma(2.0, 6.0, n)
    if n:
        flow[rng.integers(0, n, 6)] *= 7
    days = {D0 + timedelta(days=k): float(v) for k, v in enumerate(flow)}
    if gaps:
        for k in rng.integers(0, n, n // 9):
            days.pop(D0 + timedelta(days=int(k)), None)
    return days


def _as_tuple(label: FloodLabel | None) -> Any:
    return None if label is None else (label.years, label.peak, label.thresholds, label.day)


# --- 1. core/piena.py ------------------------------------------------------

RATIOS = (None, 0.0, 0.4, 0.999, 1.0, 1.6, 2.5, 9.0)
REFERENCES = (None, -3.0, 0.0, 0.7, 100.0, 1860.0)
THRESHOLDS: tuple[dict[int, float | None], ...] = (
    {2: 150.0, 5: 240.0, 20: 400.0},
    {2: 150.0, 5: None, 20: 400.0},
    {2: 150.0, 5: 0.0, 20: -1.0},
    {2: None, 5: 240.0, 20: 400.0},
    {5: 240.0, 20: 400.0},
    {2: 100.0},
    {20: 400.0, 2: 160.0, 5: 160.0},
    {},
)
DAY = date(2026, 11, 14)
FORECASTS: tuple[tuple[float, date | None] | None, ...] = (
    None,
    (160.0, DAY),
    (160.0, None),
    (161.5, DAY),
    (161.7, DAY),
    (0.3, DAY),
    (1.005, DAY),
    (250.0, DAY),
)


def test_flood_label_is_limens_piena() -> None:
    cases = list(itertools.product(RATIOS, REFERENCES, THRESHOLDS, FORECASTS))
    labelled = 0
    for ratio, reference, thresholds, forecast in cases:
        got = flood_label(ratio, reference, thresholds, forecast)
        assert _as_tuple(got) == _limen_piena(ratio, reference, thresholds, forecast)
        labelled += got is not None
    assert len(cases) == 3072
    assert labelled > 500


def test_flood_label_reads_as_limen_documents_it() -> None:
    label = flood_label(1.6, 100.0, {2: 150.0, 5: 240.0, 20: None}, (160.4, DAY))
    assert label == FloodLabel(years=2, peak=160.0, thresholds={2: 150.0, 5: 240.0}, day=DAY)
    below = flood_label(0.4, 100.0, {2: 150.0})
    assert below is not None
    assert below.years is None
    assert flood_label(1.6, 100.0, {5: 240.0}) is None
    # The label undoes discharge_ratio exactly.
    ratio = discharge_ratio(187.8, 91.3)
    recovered = flood_label(ratio, 91.3, {2: 100.0})
    assert recovered is not None
    assert recovered.peak == pytest.approx(187.8, rel=1e-12)


# --- 2. percentile_of, _node_reference, _discharge_ratios ------------------


@pytest.mark.parametrize("p", [0.0, 0.1, 0.5, 0.9, 0.95, 0.999, 1.0])
@pytest.mark.parametrize("n", [0, 1, 2, 3, 10, 365, 731])
def test_percentile_is_limens_percentile_of(n: int, p: float) -> None:
    values = list(_series(n, seed=n).values())
    assert percentile(values, p) == _limen_percentile_of(values, p)


@pytest.mark.parametrize("p", [0.5, 0.9, 0.95])
@pytest.mark.parametrize("min_days", [1, 365, 400, 2000])
@pytest.mark.parametrize("gaps", [False, True])
def test_reference_before_is_limens_node_reference(p: float, min_days: int, gaps: bool) -> None:
    daily = _series(900, seed=7, gaps=gaps)
    for start in (D0, D0 + timedelta(days=364), D0 + timedelta(days=500), D0 + timedelta(days=999)):
        before = {day: flow for day, flow in daily.items() if day < start}
        want = _limen_node_reference(before, percentile=p, min_days=min_days)
        assert reference_before(daily, start, p=p, min_days=min_days) == want
        # The form the hourly sweep uses: `references` on the bare values.
        assert references({0: list(before.values())}, p=p, min_days=min_days)[0] == want


@pytest.mark.parametrize("reference", [-1.0, 0.0, 0.5, 63.2, 1860.0])
@pytest.mark.parametrize("gaps", [False, True])
def test_peak_ratios_are_limens_discharge_ratios(reference: float, gaps: bool) -> None:
    daily = _series(400, seed=11, gaps=gaps)
    got = peak_ratios(daily, reference)
    assert got == _limen_discharge_ratios(daily, reference)
    assert list(got) == list(_limen_discharge_ratios(daily, reference))
    if reference > 0:
        assert len(got) == len(daily)


def test_peak_ratios_without_a_reference_are_empty() -> None:
    assert peak_ratios({D0: 5.0}, None) == {}
    assert peak_ratios({D0: 5.0, D0 + timedelta(days=3): 9.0}, 2.0, window_days=3) == {
        D0: 2.5,
        D0 + timedelta(days=3): 4.5,
    }


# --- 3. giorno_del_picco, giorni_dei_picchi, glofas_soglie.leggi -----------

RUN = date(2026, 11, 10)
NAN = math.nan
MEMBERS: tuple[Any, ...] = (
    [10.0, 20.0, 187.8, 150.0, 90.0],
    [[1.0, 5.0, 3.0], [2.0, 4.0, 9.0]],
    [[NAN, 5.0, 3.0], [NAN, NAN, NAN]],
    [[NAN, NAN], [NAN, NAN]],
    [NAN, NAN, NAN],
    [[7.0, 7.0, 7.0]],
    [[1.0, NAN, 8.0], [8.0, 2.0, NAN]],
    np.random.default_rng(3).gamma(2.0, 30.0, (51, 30)),
)


@pytest.mark.parametrize("members", MEMBERS)
def test_peak_day_is_limens_giorno_del_picco(members: Any) -> None:
    assert peak_day(members, RUN) == _limen_giorno_del_picco(members, RUN)


def test_peak_day_is_the_serchio_of_limens_docstring() -> None:
    # The run of the 10th peaks at the fifth lead time: the 14th.
    assert peak_day([50.0, 80.0, 120.0, 160.0, 187.8, 140.0], RUN) == date(2026, 11, 14)
    assert peak_day([NAN, NAN], RUN) is None


def test_forecast_peak_days_are_limens_giorni_dei_picchi(tmp_path: Path) -> None:
    from glofas_ewds import ensemble_members

    cube = np.random.default_rng(5).gamma(2.0, 30.0, (4, 6, 2, 2))
    cube[:, :, 1, 0] = -9999.0  # a masked cell: no forecast, so no day
    path = tmp_path / "ens.nc"
    write_cube(path, ("number", "forecast_period", "latitude", "longitude"), cube)
    nodes = [(11.83, 44.32), (11.83, 44.27), (11.88, 44.27), (2.0, 2.0)]
    want = {n: _limen_giorno_del_picco(v, RUN) for n, v in ensemble_members(path, nodes).items()}
    got = forecast_peak_days(path, nodes, RUN)
    assert got == want
    assert set(got) == {nodes[0], nodes[2]}


def _write_threshold(path: Path, values: Any, *, lat: str = "lat", lon: str = "lon") -> None:
    """A threshold file as ECMWF writes it: one 2-D variable on (lat, lon)."""
    lats = [44.425, 44.375, *LATS, 44.225]
    lons = [11.775, 11.825, *LONS, 11.975]
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension(lat, len(lats))
        ds.createDimension(lon, len(lons))
        ds.createVariable(lat, "f8", (lat,))[:] = lats
        ds.createVariable(lon, "f8", (lon,))[:] = lons
        v = ds.createVariable("rl", "f4", (lat, lon), fill_value=-9999.0)
        v[:] = np.ma.masked_invalid(np.asarray(values, dtype="f4"))


THRESHOLD_NODES = [
    (11.83, 44.32),
    (11.88, 44.27),
    (11.78, 44.42),
    (11.93, 44.22),
    (11.73, 44.37),
    (11.88, 44.37),
    (2.0, 2.0),
    (30.0, 60.0),
]


def _grid(scale: float) -> Any:
    grid = np.arange(25, dtype=float).reshape(5, 5) * scale + scale
    grid[1, 3] = NAN  # masked: sea
    grid[1, 0] = 0.0  # no river network
    grid[4, 4] = -5.0
    return grid


@pytest.mark.parametrize("names", [("lat", "lon"), ("latitude", "longitude"), ("Lat", "Lon")])
def test_read_threshold_is_limens_leggi(tmp_path: Path, names: tuple[str, str]) -> None:
    path = tmp_path / threshold_file_name(2)
    _write_threshold(path, _grid(10.0), lat=names[0], lon=names[1])
    for nodes in (THRESHOLD_NODES, THRESHOLD_NODES[:2], THRESHOLD_NODES[6:], []):
        assert read_threshold(path, nodes) == _limen_leggi(path, nodes)
    got = read_threshold(path, THRESHOLD_NODES)
    assert got[0] is not None
    assert None in got


def test_flood_thresholds_are_limens_soglie(tmp_path: Path) -> None:
    files = {}
    for years, scale in ((2, 10.0), (5, 17.0), (20, 31.0)):
        files[years] = tmp_path / threshold_file_name(years)
        _write_threshold(files[years], _grid(scale))
    got = flood_thresholds(files, THRESHOLD_NODES)
    # Limen's `soglie`: per node, the three columns of `leggi` in the order 2, 5, 20.
    columns = [_limen_leggi(files[years], THRESHOLD_NODES) for years in (2, 5, 20)]
    for i, node in enumerate(THRESHOLD_NODES):
        assert tuple(got[node][years] for years in (2, 5, 20)) == (
            columns[0][i],
            columns[1][i],
            columns[2][i],
        )
    # And what comes out goes straight into the label.
    label = flood_label(1.25, 200.0, got[THRESHOLD_NODES[0]])
    assert label is not None
    assert label.years == 5


def test_threshold_names_are_ecmwfs() -> None:
    assert threshold_file_name(2) == "flood_threshold_glofas_v4_rl_2.0.nc"
    assert threshold_url(20) == (
        "https://confluence.ecmwf.int/download/attachments/242067380/"
        "flood_threshold_glofas_v4_rl_20.0.nc"
    )


def test_a_threshold_file_that_is_not_one_says_so(tmp_path: Path) -> None:
    from glofas_ewds import GlofasEwdsError

    path = tmp_path / "two.nc"
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("lat", 2)
        ds.createDimension("lon", 2)
        ds.createVariable("a", "f4", ("lat", "lon"))
        ds.createVariable("b", "f4", ("lat", "lon"))
    with pytest.raises(GlofasEwdsError, match="one 2-D variable"):
        read_threshold(path, [(11.83, 44.32)])
    path = tmp_path / "nogrid.nc"
    with netCDF4.Dataset(path, "w") as ds:
        ds.createDimension("y", 2)
        ds.createDimension("x", 2)
        ds.createVariable("a", "f4", ("y", "x"))
    with pytest.raises(GlofasEwdsError, match="no latitude or longitude"):
        read_threshold(path, [(11.83, 44.32)])
