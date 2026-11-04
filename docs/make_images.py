"""Draw the README figures from real GloFAS 4 data.

    uv run --group docs python docs/make_images.py [--cache DIR]

The numbers come from the public Open-Meteo flood API (``seamless_v4``: GloFAS
4, consolidated where it exists, then intermediate), which needs no account,
so anyone can run this. The reference and the cell arithmetic are this
package's own functions.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from glofas_ewds import GRID_STEP, declared_cell, percentile

API = "https://flood-api.open-meteo.com/v1/flood"
START, END = date(2024, 11, 1), date(2026, 10, 31)
OUT = Path(__file__).parent / "images"

#: (label, lon, lat): a point on the river near each town.
RIVERS = [
    ("Toce at Candoglia", 8.43, 45.97),
    ("Lamone at Faenza", 11.88, 44.29),
    ("Arno at Florence", 11.25, 43.77),
]

THEMES = {
    "light": {"bg": "#ffffff", "fg": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0"},
    "dark": {"bg": "#0d1117", "fg": "#e6edf3", "muted": "#9198a1", "grid": "#30363d"},
}
LINE = {"light": ["#0969da", "#bc4c00", "#1a7f37"], "dark": ["#4493f8", "#f0883e", "#3fb950"]}


def fetch(points: list[tuple[float, float]], cache: Path) -> list[list[float]]:
    key = cache / f"{abs(hash(tuple(points))) % 10**12}.json"
    if key.exists():
        return list(json.loads(key.read_text()))
    series: list[list[float]] = []
    for k in range(0, len(points), 100):
        chunk = points[k : k + 100]
        r = httpx.get(
            API,
            params={
                "longitude": ",".join(f"{p[0]:.3f}" for p in chunk),
                "latitude": ",".join(f"{p[1]:.3f}" for p in chunk),
                "daily": "river_discharge",
                "models": "seamless_v4",
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
            },
            timeout=120,
        )
        r.raise_for_status()
        body = r.json()
        for item in body if isinstance(body, list) else [body]:
            series.append(
                [v if v is not None else float("nan") for v in item["daily"]["river_discharge"]]
            )
    cache.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(series))
    return series


def style(ax: plt.Axes, t: dict[str, str]) -> None:
    ax.set_facecolor(t["bg"])
    for s in ax.spines.values():
        s.set_color(t["grid"])
    ax.tick_params(colors=t["muted"], labelsize=9)


def cells_figure(cache: Path) -> dict[str, float]:
    lon0, lat0 = declared_cell(*RIVERS[0][1:])
    n = 3
    grid = [
        (round(lon0 + i * GRID_STEP, 3), round(lat0 - j * GRID_STEP, 3))
        for j in range(-n, n + 1)
        for i in range(-n, n + 1)
    ]
    series = fetch(grid, cache)
    ref = np.array([percentile([v for v in s if v == v], 0.9) or np.nan for s in series])
    ref = ref.reshape(2 * n + 1, 2 * n + 1)
    centre = float(ref[n, n])
    west, east = float(ref[n, n - 1]), float(ref[n, n + 1])
    for name, t in THEMES.items():
        fig, ax = plt.subplots(figsize=(7.2, 6.0), dpi=150)
        fig.patch.set_facecolor(t["bg"])
        style(ax, t)
        extent = (
            lon0 - (n + 0.5) * GRID_STEP,
            lon0 + (n + 0.5) * GRID_STEP,
            lat0 - (n + 0.5) * GRID_STEP,
            lat0 + (n + 0.5) * GRID_STEP,
        )
        im = ax.imshow(
            np.clip(ref, 0.1, None),
            extent=extent,
            cmap="Blues" if name == "light" else "viridis",
            norm=LogNorm(vmin=0.1, vmax=float(np.nanmax(ref))),
            origin="upper",
        )
        for j in range(2 * n + 1):
            for i in range(2 * n + 1):
                v = ref[j, i]
                x, y = lon0 + (i - n) * GRID_STEP, lat0 - (j - n) * GRID_STEP
                ax.text(
                    x,
                    y,
                    f"{v:.0f}" if v >= 10 else f"{v:.1f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="#ffffff" if (v > 20) == (name == "light") else "#000000",
                )
        for dx in (0, -1, 1):
            x = lon0 + dx * GRID_STEP
            ax.add_patch(
                plt.Rectangle(
                    (x - GRID_STEP / 2, lat0 - GRID_STEP / 2),
                    GRID_STEP,
                    GRID_STEP,
                    fill=False,
                    lw=2.2,
                    ec="#cf222e" if dx == 0 else t["fg"],
                )
            )
        ax.plot(*RIVERS[0][1:], marker="x", color="#cf222e", ms=9, mew=2)
        ax.set_title(
            "Toce near Candoglia: the 90th percentile of daily discharge\n"
            "in each 0.05° GloFAS 4 cell, m³/s (Nov 2024 - Oct 2026)",
            color=t["fg"],
            fontsize=11,
        )
        ax.set_xlabel("longitude", color=t["muted"])
        ax.set_ylabel("latitude", color=t["muted"])
        cb = fig.colorbar(im, ax=ax, shrink=0.85)
        cb.ax.tick_params(colors=t["muted"], labelsize=8)
        cb.outline.set_edgecolor(t["grid"])  # type: ignore[union-attr]
        fig.tight_layout()
        fig.savefig(OUT / f"cells-{name}.png", facecolor=t["bg"])
        plt.close(fig)
    return {"centre": centre, "west": west, "east": east}


def series_figure(cache: Path) -> dict[str, dict[str, float]]:
    days = np.arange(np.datetime64(START), np.datetime64(END) + np.timedelta64(1, "D"))
    facts: dict[str, dict[str, float]] = {}
    picked: list[tuple[str, list[float], float]] = []
    for label, lon, lat in RIVERS:
        c = declared_cell(lon, lat)
        around = [
            (round(c[0] + i * GRID_STEP, 3), round(c[1] + j * GRID_STEP, 3))
            for j in (-1, 0, 1)
            for i in (-1, 0, 1)
        ]
        all_series = fetch(around, cache)
        # The main channel: the cell of the nine with the largest flow.
        best = max(all_series, key=lambda s: np.nanmean(s))
        p90 = percentile([v for v in best if v == v], 0.9) or float("nan")
        picked.append((label, best, p90))
        facts[label] = {
            "p90": p90,
            "peak": float(np.nanmax(best)),
            "ratio": float(np.nanmax(best)) / p90,
        }
    for name, t in THEMES.items():
        fig, axes = plt.subplots(len(picked), 1, figsize=(8.4, 6.6), dpi=150, sharex=True)
        fig.patch.set_facecolor(t["bg"])
        for ax, (label, s, p90), colour in zip(axes, picked, LINE[name], strict=True):
            style(ax, t)
            ax.plot(days, s, color=colour, lw=1.1)
            ax.axhline(p90, color=t["fg"], lw=1, ls="--")
            ax.fill_between(days, p90, s, where=np.array(s) > p90, color=colour, alpha=0.25)
            ax.text(
                days[5],
                p90,
                f" ordinary high flow (90th pct) {p90:.0f} m³/s",
                va="bottom",
                color=t["fg"],
                fontsize=8,
            )
            ax.set_title(
                f"{label}: peak {np.nanmax(s):.0f} m³/s = {np.nanmax(s) / p90:.1f}x its own reference",
                color=t["fg"],
                fontsize=10,
                loc="left",
            )
            ax.set_ylabel("m³/s", color=t["muted"])
            ax.grid(color=t["grid"], lw=0.5)
        fig.suptitle("GloFAS 4 daily discharge, Nov 2024 - Oct 2026", color=t["fg"], fontsize=11)
        fig.tight_layout()
        fig.savefig(OUT / f"series-{name}.png", facecolor=t["bg"])
        plt.close(fig)
    return facts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(".cache/open-meteo"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("cells", cells_figure(args.cache))
    for label, f in series_figure(args.cache).items():
        print(label, {k: round(v, 2) for k, v in f.items()})


if __name__ == "__main__":
    main()
