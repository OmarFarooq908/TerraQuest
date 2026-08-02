"""Deprecated shim — use adventure_packbuilder.discovery.run_discovery."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from adventure_core.catalog import DiscoveryConfig

from adventure_packbuilder.discovery.pipeline import run_discovery, write_geojson

__all__ = ["build_seeds", "write_geojson", "run_discovery"]


def build_seeds(
    layers: dict[str, dict],
    *,
    dem_paths: list | None = None,
    limits: dict[str, int] | None = None,
    bbox: list[float] | None = None,
    discovery: dict[str, Any] | DiscoveryConfig | None = None,
) -> dict[str, Any]:
    """Deprecated: use :func:`run_discovery`."""
    warnings.warn(
        "build_seeds() is deprecated; use adventure_packbuilder.run_discovery()",
        DeprecationWarning,
        stacklevel=2,
    )
    if bbox is None:
        xs: list[float] = []
        ys: list[float] = []
        for key in ("settlements", "water", "road_nodes", "peaks"):
            for feat in (layers.get(key) or {}).get("features", []):
                geom = feat.get("geometry") or {}
                if geom.get("type") == "Point":
                    xs.append(float(geom["coordinates"][0]))
                    ys.append(float(geom["coordinates"][1]))
        if xs and ys:
            pad = 0.01
            bbox = [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]
        else:
            bbox = [0.0, 0.0, 1.0, 1.0]

    cfg: dict[str, Any] | DiscoveryConfig | None = discovery
    if cfg is None and limits:
        cfg = {
            "generators": {
                "named_waterbody": {"quota": limits.get("max_water", 20) // 2 + 1},
                "unnamed_waterbody": {"quota": limits.get("max_water", 20) // 2 + 1},
                "osm_peak": {"quota": limits.get("max_peaks", 15)},
                "osm_viewpoint": {"quota": limits.get("max_viewpoints", 10)},
                "track_terminus": {"quota": limits.get("max_tracks", 25)},
            }
        }

    result = run_discovery(
        layers,
        bbox=bbox,
        dem_paths=[Path(p) for p in (dem_paths or [])],
        discovery=cfg,
    )
    result["seeds"] = result["catalog"]
    result["stats"]["seed_count"] = result["stats"]["catalog_count"]
    return result
