"""Orchestrate named generators → catalog with quotas + spatial diversity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adventure_core.catalog import CATALOG_SCHEMA_VERSION, CatalogCandidate, DiscoveryConfig

from adventure_packbuilder.dem import local_relief_from_dem, sample_elevations
from adventure_packbuilder.discovery.context import build_context
from adventure_packbuilder.discovery.diversity import merge_catalog_diverse, select_diverse
from adventure_packbuilder.discovery.generators import GENERATORS

DEFAULT_QUOTAS: dict[str, int] = {
    "track_terminus": 25,
    "road_spur": 20,
    "unnamed_waterbody": 20,
    "named_waterbody": 15,
    "isolation_maximum": 20,
    "dem_local_max": 15,
    "terrain_relief_hotspot": 15,
    "osm_peak": 15,
    "osm_viewpoint": 10,
}


def _enrich_dem(candidates: list[CatalogCandidate], dem_paths: list[Path]) -> None:
    if not candidates:
        return
    coords = [(c.lon, c.lat) for c in candidates]
    if dem_paths:
        elevs = sample_elevations(coords, dem_paths)
    else:
        elevs = [None] * len(candidates)
    for cand, elev in zip(candidates, elevs, strict=True):
        if elev is not None:
            cand.elevation_m = round(float(elev), 1)
        elif cand.elevation_m is None:
            cand.elevation_m = 0.0
        if dem_paths:
            relief = local_relief_from_dem(cand.lon, cand.lat, dem_paths)
            cand.relief_m = round(relief, 1)
            cand.evidence["elevation_m"] = cand.elevation_m
            cand.evidence["relief_m"] = cand.relief_m
            if "dem" not in cand.provenance.sources:
                cand.provenance.sources = list(cand.provenance.sources) + ["dem"]
        elif cand.relief_m is None:
            cand.relief_m = 0.0


def run_discovery(
    layers: dict[str, dict],
    *,
    bbox: list[float],
    dem_paths: list[Path] | None = None,
    discovery: DiscoveryConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all generators; return catalog FeatureCollection + stats."""
    if isinstance(discovery, DiscoveryConfig):
        cfg = discovery
    elif isinstance(discovery, dict):
        cfg = DiscoveryConfig.model_validate(discovery)
    else:
        cfg = DiscoveryConfig()

    # Fill default generator quotas if unset
    for name, quota in DEFAULT_QUOTAS.items():
        if name not in cfg.generators:
            from adventure_core.catalog import GeneratorQuota

            cfg.generators[name] = GeneratorQuota(quota=quota)

    ctx = build_context(layers, bbox=bbox, config=cfg, dem_paths=dem_paths)
    per_gen: dict[str, list[CatalogCandidate]] = {}
    raw_counts: dict[str, int] = {}

    for name, fn in GENERATORS.items():
        quota = cfg.quota_for(name, DEFAULT_QUOTAS.get(name, 20))
        if quota <= 0:
            raw_counts[name] = 0
            per_gen[name] = []
            continue
        raw = fn(ctx)
        raw_counts[name] = len(raw)
        selected = select_diverse(
            raw,
            quota=quota,
            min_spacing_km=cfg.spacing_for(name),
        )
        per_gen[name] = selected

    catalog = merge_catalog_diverse(
        list(per_gen.values()),
        global_min_spacing_km=min(0.35, cfg.min_spacing_km),
    )
    _enrich_dem(catalog, list(dem_paths or []))

    # Stable order: generator name then id
    catalog.sort(key=lambda c: (c.generator, c.id))

    features = [c.to_geojson_feature() for c in catalog]
    elev_features: list[dict] = []
    for c in catalog:
        elev_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
                "properties": {
                    "id": f"elev_{c.id}",
                    "elevation_m": c.elevation_m or 0.0,
                    "relief_m": c.relief_m or 0.0,
                },
            }
        )

    stats = {
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_count": len(catalog),
        "with_dem_elevation": sum(1 for c in catalog if c.elevation_m and c.elevation_m > 0),
        "raw_by_generator": raw_counts,
        "selected_by_generator": {k: len(v) for k, v in per_gen.items()},
        "quotas": {k: cfg.quota_for(k) for k in GENERATORS},
        "min_spacing_km": cfg.min_spacing_km,
        "spacing_by_generator": {k: cfg.spacing_for(k) for k in GENERATORS},
        "grid_res_deg": cfg.grid_res_deg,
        "generators_run": list(GENERATORS.keys()),
    }
    return {
        "catalog": {"type": "FeatureCollection", "features": features},
        "elevation": {"type": "FeatureCollection", "features": elev_features},
        "stats": stats,
        "candidates": catalog,
    }


def write_geojson(path: Path, fc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
