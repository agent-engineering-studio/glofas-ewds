"""GloFAS river discharge and the Copernicus fire danger indices from the EWDS,
read on the right grid cell."""

from glofas_ewds.cells import GRID_STEP, Node, cell_indices, declared_cell, open_meteo_cell
from glofas_ewds.client import EWDS_URL, EwdsClient, cdsapi_client
from glofas_ewds.download import Retriever, download_fire, download_forecast, download_history
from glofas_ewds.errors import GlofasEwdsError
from glofas_ewds.fwi import FIRE_DATASET, FIRE_VARIABLES, fire_request, fire_values
from glofas_ewds.glofas import discharge_series, forecast_peaks
from glofas_ewds.reference import MIN_REFERENCE_DAYS, discharge_ratio, percentile, references
from glofas_ewds.request import (
    FORECAST_DATASET,
    GLOFAS_VERSION,
    HISTORICAL_DATASET,
    HISTORY_LATENCY_DAYS,
    ITALY,
    Area,
    candidate_runs,
    forecast_request,
    historical_request,
    months,
)

__version__ = "0.1.0"

__all__ = [
    "EWDS_URL",
    "FIRE_DATASET",
    "FIRE_VARIABLES",
    "FORECAST_DATASET",
    "GLOFAS_VERSION",
    "GRID_STEP",
    "HISTORICAL_DATASET",
    "HISTORY_LATENCY_DAYS",
    "ITALY",
    "MIN_REFERENCE_DAYS",
    "Area",
    "EwdsClient",
    "GlofasEwdsError",
    "Node",
    "Retriever",
    "__version__",
    "candidate_runs",
    "cdsapi_client",
    "cell_indices",
    "declared_cell",
    "discharge_ratio",
    "discharge_series",
    "download_fire",
    "download_forecast",
    "download_history",
    "fire_request",
    "fire_values",
    "forecast_peaks",
    "forecast_request",
    "historical_request",
    "months",
    "open_meteo_cell",
    "percentile",
    "references",
]
