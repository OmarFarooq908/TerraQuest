"""Offline tests for the deterministic discovery pipeline."""

from __future__ import annotations

from adventure_core.catalog import CatalogCandidate, DensifyHook, DiscoveryConfig, Provenance
from adventure_packbuilder.discovery.diversity import select_diverse
from adventure_packbuilder.discovery.pipeline import run_discovery


def _pt(lon: float, lat: float, **props):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _line(coords, **props):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


def test_select_diverse_respects_quota_and_spacing():
    cands = []
    for i in range(10):
        cands.append(
            CatalogCandidate(
                id=f"c{i}",
                name=f"c{i}",
                lon=75.0 + i * 0.02,  # ~1.8 km steps at this latitude
                lat=35.0,
                kind="x",
                generator="track_terminus",
                provenance=Provenance(sources=["osm"], method="test"),
                evidence={"discovery_score": float(10 - i)},
                densify=DensifyHook(cell_id=f"c{i}"),
            )
        )
    selected = select_diverse(cands, quota=3, min_spacing_km=0.5)
    assert len(selected) == 3
    assert selected[0].id == "c0"


def test_run_discovery_emits_generator_metadata():
    layers = {
        "settlements": {
            "type": "FeatureCollection",
            "features": [
                _pt(75.5, 35.3, id="n/1", name="Skardu", place="town", osm_id=1, osm_type="node"),
            ],
        },
        "water": {
            "type": "FeatureCollection",
            "features": [
                _pt(
                    75.55,
                    35.35,
                    id="w/2",
                    name="Satpara Lake",
                    kind="lake",
                    has_water=True,
                    osm_id=2,
                    osm_type="way",
                ),
                _pt(
                    75.6,
                    35.4,
                    id="w/3",
                    name="unnamed_lake_3",
                    kind="lake",
                    has_water=True,
                    osm_id=3,
                    osm_type="way",
                ),
            ],
        },
        "road_nodes": {
            "type": "FeatureCollection",
            "features": [
                _pt(75.52, 35.32, id="r/4", highway="track", osm_id=4, osm_type="way", name="t"),
                _pt(
                    75.51,
                    35.31,
                    id="r/5",
                    highway="secondary",
                    osm_id=5,
                    osm_type="way",
                    name="main",
                ),
            ],
        },
        "road_lines": {
            "type": "FeatureCollection",
            "features": [
                _line(
                    [[75.51, 35.31], [75.52, 35.32], [75.58, 35.42]],
                    id="way/4",
                    highway="track",
                    osm_id=4,
                    osm_type="way",
                    name="spur",
                ),
            ],
        },
        "peaks": {
            "type": "FeatureCollection",
            "features": [
                _pt(
                    75.7,
                    35.45,
                    id="p/6",
                    name="Peak A",
                    osm_id=6,
                    osm_type="node",
                    elevation_m=4500,
                ),
            ],
        },
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    result = run_discovery(
        layers,
        bbox=[75.35, 35.20, 75.75, 35.50],
        dem_paths=[],
        discovery=DiscoveryConfig(
            min_spacing_km=0.3,
            grid_res_deg=0.05,
            generators={
                "named_waterbody": {"quota": 5},
                "unnamed_waterbody": {"quota": 5},
                "track_terminus": {"quota": 5},
                "road_spur": {"quota": 5},
                "isolation_maximum": {"quota": 5},
                "dem_local_max": {"quota": 0},
                "terrain_relief_hotspot": {"quota": 0},
                "osm_peak": {"quota": 5},
                "osm_viewpoint": {"quota": 0},
            },
        ),
    )
    feats = result["catalog"]["features"]
    assert len(feats) >= 3
    generators = {f["properties"]["generator"] for f in feats}
    assert "named_waterbody" in generators
    assert "osm_peak" in generators
    for f in feats:
        p = f["properties"]
        assert p["generator"]
        assert p["provenance"]["method"]
        assert "densify" in p and p["densify"]["cell_id"]
        assert "evidence" in p
    assert result["stats"]["catalog_schema_version"] == "0.3.0"
