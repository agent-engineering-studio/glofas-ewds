# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

