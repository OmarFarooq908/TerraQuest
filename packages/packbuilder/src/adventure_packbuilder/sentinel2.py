"""Attach optional Sentinel-2 index layer at pack build (RFC-0006 / issue #21)."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

from adventure_core.config import repo_root
from adventure_core.pack_manifest import PackManifest, PackSource

SENTINEL_LAYER_NAME = "sentinel_indices.geojson"


class Sentinel2BuildError(RuntimeError):
    """Misconfigured or incomplete Sentinel-2 pack build options."""


def _validate_lon_lat(coords: Any, *, index: int) -> tuple[float, float]:
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        raise Sentinel2BuildError(
            f"sentinel indices features[{index}] coordinates must be [lon, lat]"
        )
    try:
        lon = float(coords[0])
        lat = float(coords[1])
    except (TypeError, ValueError) as exc:
        raise Sentinel2BuildError(
            f"sentinel indices features[{index}] coordinates must be numeric"
        ) from exc
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise Sentinel2BuildError(f"sentinel indices features[{index}] coordinates must be finite")
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise Sentinel2BuildError(f"sentinel indices features[{index}] lon/lat out of WGS84 range")
    return lon, lat


def _normalize_indices_fc(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("type") != "FeatureCollection":
        raise Sentinel2BuildError("sentinel indices GeoJSON must be a FeatureCollection")
    features = raw.get("features")
    if not isinstance(features, list):
        raise Sentinel2BuildError("sentinel indices FeatureCollection missing features[]")
    if not features:
        raise Sentinel2BuildError(
            "sentinel indices FeatureCollection is empty — disable sentinel2 or provide samples"
        )
    out: list[dict[str, Any]] = []
    seen_catalog: set[str] = set()
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            raise Sentinel2BuildError(f"sentinel indices features[{i}] must be an object")
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            raise Sentinel2BuildError(f"sentinel indices features[{i}] must be Point geometry")
        lon, lat = _validate_lon_lat(geom.get("coordinates"), index=i)
        props = dict(feat.get("properties") or {})
        catalog_id = props.get("catalog_id")
        if catalog_id is None or str(catalog_id).strip() == "":
            raise Sentinel2BuildError(
                f"sentinel indices features[{i}] missing required properties.catalog_id"
            )
        catalog_id_s = str(catalog_id).strip()
        if catalog_id_s in seen_catalog:
            raise Sentinel2BuildError(
                f"sentinel indices duplicate catalog_id {catalog_id_s!r} "
                f"(features must be 1:1 with catalog)"
            )
        seen_catalog.add(catalog_id_s)
        props["catalog_id"] = catalog_id_s
        props.setdefault("index_version", "s2-indices-v1")
        out.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
                **({"id": feat["id"]} if "id" in feat else {}),
            }
        )
    return {"type": "FeatureCollection", "features": out}


def clear_sentinel_layer(layers_dir: Path) -> bool:
    """Remove a leftover ``sentinel_indices.geojson`` (e.g. after disabling)."""
    path = layers_dir / SENTINEL_LAYER_NAME
    if path.is_file():
        path.unlink()
        return True
    return False


def maybe_attach_sentinel_indices(
    config: PackManifest,
    layers_dir: Path,
) -> tuple[PackSource | None, bool]:
    """Copy precomputed indices into the pack when ``sentinel2.enabled``.

    Returns ``(source_or_none, wrote_layer)``. When disabled, any leftover
    ``sentinel_indices.geojson`` from a prior build is removed so validate/hash
    stay consistent. Live STAC download is intentionally out of band — see
    RFC-0006 Skardu pilot recipe.
    """
    cfg = dict(config.sentinel2 or {})
    if not cfg.get("enabled"):
        clear_sentinel_layer(layers_dir)
        return None, False

    raw_path = cfg.get("indices_geojson")
    if not raw_path:
        raise Sentinel2BuildError(
            "sentinel2.enabled is true but sentinel2.indices_geojson is unset. "
            "Precompute a Point FeatureCollection (NDVI/NDWI per catalog_id) and "
            "point this path at it — see RFC-0006 / docs/pack-builder.md. "
            "Live STAC fetch inside pack build is not enabled yet."
        )

    src = Path(str(raw_path))
    if not src.is_absolute():
        src = repo_root() / src
    if not src.is_file():
        raise Sentinel2BuildError(f"sentinel2.indices_geojson not found: {src}")

    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Sentinel2BuildError(f"sentinel2.indices_geojson is not valid JSON: {src}") from exc
    if not isinstance(raw, dict):
        raise Sentinel2BuildError("sentinel indices GeoJSON root must be an object")

    normalized = _normalize_indices_fc(raw)
    dest = layers_dir / SENTINEL_LAYER_NAME
    dest.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")

    source = PackSource(
        kind="sentinel2",
        provider=str(cfg.get("provider") or "Copernicus Sentinel-2 L2A (precomputed indices)"),
        retrieved_at=cfg.get("retrieved_at"),
        license=str(
            cfg.get("license")
            or "Copernicus Sentinel data — https://sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice"
        ),
        attribution=str(cfg.get("attribution") or "Contains modified Copernicus Sentinel data"),
        url=cfg.get("stac_api") or cfg.get("url"),
        content_hash=None,
        extra={
            "indices": list(cfg.get("indices") or ["ndvi", "ndwi"]),
            "max_cloud_cover": cfg.get("max_cloud_cover", 20),
            "indices_geojson": str(src),
            "feature_count": len(normalized["features"]),
            "index_version": "s2-indices-v1",
        },
    )
    cache_hint = cfg.get("cache_copy")
    if cache_hint:
        cache_path = Path(str(cache_hint))
        if not cache_path.is_absolute():
            cache_path = repo_root() / cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, cache_path)
    return source, True
