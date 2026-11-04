"""The exceptions this package raises."""

from __future__ import annotations


class GlofasEwdsError(Exception):
    """An EWDS request failed, or a file is not one this package can read."""


__all__ = ["GlofasEwdsError"]
