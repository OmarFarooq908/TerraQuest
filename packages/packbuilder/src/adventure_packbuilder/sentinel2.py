"""Attach optional Sentinel-2 index layer at pack build (RFC-0006 / issue #21)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from adventure_core.config import repo_root
from adventure_core.pack_manifest import PackManifest, PackSource


class Sentinel2BuildError(RuntimeError):
    """Misconfigured or incomplete Sentinel-2 pack build options."""


def _normalize_indices_fc(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("type") != "FeatureCollection":
        raise Sentinel2BuildError("sentinel indices GeoJSON must be a FeatureCollection")
    features = raw.get("features")
    if not isinstance(features, list):
        raise Sentinel2BuildError("sentinel indices FeatureCollection missing features[]")
    out: list[dict[str, Any]] = []
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            raise Sentinel2BuildError(f"sentinel indices features[{i}] must be an object")
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            raise Sentinel2BuildError(f"sentinel indices features[{i}] must be Point geometry")
        props = dict(feat.get("properties") or {})
        if not props.get("catalog_id"):
            raise Sentinel2BuildError(
                f"sentinel indices features[{i}] missing required properties.catalog_id"
            )
        props.setdefault("index_version", "s2-indices-v1")
        out.append(
            {
                "type": "Feature",
                "geometry": geom,
                "properties": props,
                **({"id": feat["id"]} if "id" in feat else {}),
            }
        )
    return {"type": "FeatureCollection", "features": out}


def maybe_attach_sentinel_indices(
    config: PackManifest,
    layers_dir: Path,
) -> tuple[PackSource | None, bool]:
    """Copy precomputed indices into the pack when ``sentinel2.enabled``.

    Returns ``(source_or_none, wrote_layer)``. Live STAC download is intentionally
    out of band — see RFC-0006 Skardu pilot recipe.
    """
    cfg = dict(config.sentinel2 or {})
    if not cfg.get("enabled"):
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

    raw = json.loads(src.read_text(encoding="utf-8"))
    normalized = _normalize_indices_fc(raw)
    dest = layers_dir / "sentinel_indices.geojson"
    dest.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")

    source = PackSource(
        kind="sentinel2",
        provider=str(cfg.get("provider") or "Copernicus Sentinel-2 L2A (precomputed indices)"),
        retrieved_at=cfg.get("retrieved_at"),
        license=str(
            cfg.get("license")
            or "Copernicus Sentinel data — https://sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice"
        ),
        attribution=str(
            cfg.get("attribution")
            or "Contains modified Copernicus Sentinel data"
        ),
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
    # Keep a copy under cache for rebuilds when builders pass a transient path.
    cache_hint = cfg.get("cache_copy")
    if cache_hint:
        cache_path = Path(str(cache_hint))
        if not cache_path.is_absolute():
            cache_path = repo_root() / cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, cache_path)
    return source, True
