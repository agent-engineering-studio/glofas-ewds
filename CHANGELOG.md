# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- The documentation site is built with [Zensical](https://zensical.org)
  (`zensical.toml`) instead of MkDocs; `mkdocs.yml` and `mkdocs-material` are
  gone. Same pages, same URLs.

## [0.2.0] - 2026-11-05

> Released before the first live run. On 2026-11-05 `live.yml` passed against
> the real EWDS, including the ensemble file. The control run is unchanged
> from 0.1.

### Added

- Live contract tests (`tests/test_live.py`, marker `live`, `GLOFAS_EWDS_LIVE=1`
  and an EWDS key): the cell one step east, the same numbers as Open-Meteo's
  `consolidated_v4`, the history latency and the intermediate fallback, the
  shape of the forecast file, the FWI names. Weekly in CI (`live.yml`); a
  failure opens an issue, and with an `ANTHROPIC_API_KEY` secret Claude adds
  a diagnosis from the log.
- README trap 11: Open-Meteo's history after 2024 is its forecast archive,
  not the reanalysis.
- The ensemble: `forecast_request(product=ENSEMBLE)`, `download_ensemble`,
  `EwdsClient.ensemble`, `ensemble_members` (member, lead time) per node, and
  the pure `exceedance_probability` / `exceedance_by_lead`.
- Return levels from a node's own reanalysis: `discharge_by_day`,
  `annual_maxima`, `gumbel_fit` (L-moments), `return_level`, `return_levels`.
  Not the official GloFAS thresholds, which the EWDS does not serve.

### Changed

- Forecast files are read by the names of their dimensions (member, lead
  time, run, latitude, longitude), so the control run and the ensemble share
  one reader; a 4-D file with unknown names is read as before, by position,
  and anything else raises `GlofasEwdsError` naming its dimensions.
  `forecast_peaks` on an ensemble file is the peak over all members.

## [0.1.0] - 2026-11-04

### Added

- `open_meteo_cell` and `declared_cell`: the GloFAS 4 cell Open-Meteo serves
  for a point (float32, rounded away from zero, one step east of the one it
  declares), and `cell_indices` to find it in a file.
- Request builders for the EWDS: `historical_request` (GloFAS 4, consolidated
  or intermediate), `forecast_request` (00 UTC control run), `fire_request`
  (`cems-fire-historical-v1`), `months`, `candidate_runs`.
- Re-runnable downloads with any `retrieve` client: `download_history`,
  `download_forecast`, `download_fire` (intermediate only on "not a valid
  combination"; `.part` then rename), and the async `EwdsClient`.
- NetCDF readers (extra `netcdf`): `discharge_series`, `forecast_peaks`,
  `fire_values` (FWI components by `long_name`).
- `percentile`, `references`, `discharge_ratio`.
- Extracted from Limen; parity on 36,637 points and on every request.

