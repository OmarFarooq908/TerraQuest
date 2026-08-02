"""Minimal geospatial helpers — no GDAL required for the vertical slice."""

from __future__ import annotations

import math
from typing import NamedTuple


class Point(NamedTuple):
    lon: float
    lat: float


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
