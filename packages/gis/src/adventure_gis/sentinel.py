"""Sentinel-2 index join helpers (RFC-0006 / issue #21)."""

from __future__ import annotations

from adventure_core.geo import Point, haversine_km

from adventure_gis.pack_data import NamedPoint

# Match radius when catalog_id is missing on an index feature.
SENTINEL_MATCH_RADIUS_KM = 0.25


def _optional_index(props: dict, key: str) -> float | None:
    raw = props.get(key)
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val != val:  # NaN
        return None
    return max(-1.0, min(1.0, val))


def lookup_sentinel_indices(
    catalog_id: str,
    origin: Point,
    indices: list[NamedPoint],
    *,
    match_radius_km: float = SENTINEL_MATCH_RADIUS_KM,
) -> tuple[float | None, float | None, dict]:
    """Return ``(ndvi, ndwi, meta)`` for a catalog point.

    Prefer exact ``properties.catalog_id``; else nearest point within
    ``match_radius_km``. Empty ``indices`` → all null / empty meta.
    """
    if not indices:
        return None, None, {}

    by_catalog = {
        str(pt.properties.get("catalog_id")): pt
        for pt in indices
        if pt.properties.get("catalog_id")
    }
    hit = by_catalog.get(catalog_id)
    via = "catalog_id"
    if hit is None:
        best: tuple[float, NamedPoint] | None = None
        for pt in indices:
            d = haversine_km(origin, pt.point)
            if d <= match_radius_km and (best is None or d < best[0]):
                best = (d, pt)
        if best is None:
            return None, None, {}
        hit = best[1]
        via = "distance"

    props = hit.properties
    ndvi = _optional_index(props, "ndvi")
    ndwi = _optional_index(props, "ndwi")
    meta = {
        "match_via": via,
        "index_feature_id": hit.id,
        "cloud_cover": props.get("cloud_cover"),
        "acquired_at": props.get("acquired_at"),
        "stac_item_id": props.get("stac_item_id"),
        "index_version": props.get("index_version") or "s2-indices-v1",
    }
    return ndvi, ndwi, meta
