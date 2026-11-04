from __future__ import annotations

from types import ModuleType

from glofas_ewds.errors import GlofasEwdsError


def netcdf4() -> ModuleType:
    try:
        import netCDF4
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise GlofasEwdsError(
            "reading EWDS files needs netCDF4: pip install 'glofas-ewds[netcdf]'"
        ) from exc
    return netCDF4
