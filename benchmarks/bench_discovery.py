#!/usr/bin/env python3
"""Smoke benchmark: discovery on tiny synthetic layers (offline)."""

from __future__ import annotations

import time

from adventure_core.catalog import DiscoveryConfig
from adventure_packbuilder.discovery import run_discovery


def _pt(lon: float, lat: float, **props: object) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def main() -> None:
    layers = {
        "settlements": {
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, id="n/1", name="Town", place="town", osm_id=1)],
        },
        "water": {
            "type": "FeatureCollection",
            "features": [
                _pt(75.55, 35.35, id="w/2", name="Lake", kind="lake", osm_id=2, has_water=True)
            ],
        },
        "road_nodes": {"type": "FeatureCollection", "features": []},
        "road_lines": {"type": "FeatureCollection", "features": []},
        "peaks": {"type": "FeatureCollection", "features": []},
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    t0 = time.perf_counter()
    result = run_discovery(
        layers,
        bbox=[75.4, 35.2, 75.7, 35.5],
        dem_paths=[],
        discovery=DiscoveryConfig(grid_res_deg=0.05, min_spacing_km=0.3),
    )
    dt = time.perf_counter() - t0
    print(f"catalog={result['stats']['catalog_count']} seconds={dt:.4f}")


if __name__ == "__main__":
    main()
