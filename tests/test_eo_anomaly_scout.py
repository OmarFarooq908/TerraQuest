"""EO texture anomaly scout + verified pack import (RFC-0010)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from adventure_core.catalog import DiscoveryConfig
from adventure_core.evidence_ledger import validate_evidence_ledger
from adventure_packbuilder.discovery.context import build_context
from adventure_packbuilder.discovery.generators import gen_eo_texture_anomaly
from adventure_packbuilder.discovery.pipeline import run_discovery
from adventure_packbuilder.eo_anomaly import (
    EoAnomalyError,
    candidates_to_geojson,
    load_verified_scout_features,
    scout_texture_anomalies,
    write_scout_geojson,
    write_scout_gpx,
)


def _write_contrast_tif(path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    # Two-band 32x32: smooth background + a compact bright square (NIR/SWIR NDMI edge).
    h = w = 32
    nir = np.full((h, w), 0.3, dtype=np.float32)
    swir = np.full((h, w), 0.3, dtype=np.float32)
    nir[12:18, 12:18] = 0.9
    swir[12:18, 12:18] = 0.1
    transform = from_origin(75.0, 35.5, 0.001, 0.001)  # west, north, xsize, ysize
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=2,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as ds:
        ds.write(nir, 1)
        ds.write(swir, 2)


def test_scout_finds_compact_cluster(tmp_path: Path) -> None:
    tif = tmp_path / "snippet.tif"
    _write_contrast_tif(tif)
    cands = scout_texture_anomalies(
        tif,
        nir_band=1,
        swir_band=2,
        edge_threshold=0.2,
        min_pixels=3,
        max_pixels=200,
    )
    assert len(cands) >= 1
    assert all(c["verified"] is False for c in cands)
    lon, lat = cands[0]["coordinates"]
    assert 74.9 < lon < 75.2
    assert 35.4 < lat < 35.6
    geo = write_scout_geojson(tmp_path / "raw.geojson", cands)
    gpx = write_scout_gpx(tmp_path / "raw.gpx", cands)
    assert geo.is_file()
    assert "wpt" in gpx.read_text(encoding="utf-8")
    fc = json.loads(geo.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    assert fc["features"][0]["properties"]["verified"] is False


def test_load_verified_only(tmp_path: Path) -> None:
    fc = candidates_to_geojson(
        [
            {
                "id": "A",
                "type": "texture_anomaly",
                "coordinates": [75.1, 35.3],
                "verified": False,
                "metrics": {"pixel_size": 8, "edge_intensity": 0.5},
                "index_name": "ndmi",
            },
            {
                "id": "B",
                "type": "texture_anomaly",
                "coordinates": [75.2, 35.4],
                "verified": True,
                "metrics": {"pixel_size": 10, "edge_intensity": 0.7},
                "index_name": "ndmi",
            },
        ]
    )
    # Force verified flags onto properties (candidates_to_geojson already does).
    fc["features"][0]["properties"]["verified"] = False
    fc["features"][1]["properties"]["verified"] = True
    path = tmp_path / "mixed.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")
    kept = load_verified_scout_features(path, bbox=[75.0, 35.0, 76.0, 36.0])
    assert len(kept) == 1
    assert kept[0]["properties"]["id"] == "B"


def test_generator_imports_verified_features() -> None:
    layers = {
        "settlements": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [75.4, 35.3]},
                    "properties": {"id": "s1", "name": "town"},
                }
            ],
        },
        "water": {"type": "FeatureCollection", "features": []},
        "road_nodes": {"type": "FeatureCollection", "features": []},
        "road_lines": {"type": "FeatureCollection", "features": []},
        "peaks": {"type": "FeatureCollection", "features": []},
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    feats = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [75.5, 35.4]},
            "properties": {
                "id": "EO_001",
                "verified": True,
                "pixel_size": 14,
                "edge_intensity": 0.8,
                "index_name": "ndmi",
                "raster": "snippet.tif",
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [75.55, 35.42]},
            "properties": {
                "id": "EO_SKIP",
                "verified": False,
                "pixel_size": 9,
                "edge_intensity": 0.4,
                "index_name": "ndmi",
            },
        },
    ]
    cfg = DiscoveryConfig(
        min_spacing_km=0.1,
        generators={"eo_texture_anomaly": {"quota": 10}},
    )
    ctx = build_context(
        layers,
        bbox=[75.35, 35.20, 75.85, 35.55],
        config=cfg,
        eo_scout_features=feats,
    )
    out = gen_eo_texture_anomaly(ctx)
    assert len(out) == 1
    assert out[0].generator == "eo_texture_anomaly"
    assert out[0].evidence["pixel_size"] == 14
    assert "eo" in out[0].provenance.sources
    errs = validate_evidence_ledger(
        generator=out[0].generator,
        provenance=out[0].provenance.model_dump(),
        evidence=out[0].evidence,
        feature_id=out[0].id,
    )
    assert errs == []


def test_run_discovery_quota_zero_skips_eo() -> None:
    layers = {
        "settlements": {"type": "FeatureCollection", "features": []},
        "water": {"type": "FeatureCollection", "features": []},
        "road_nodes": {"type": "FeatureCollection", "features": []},
        "road_lines": {"type": "FeatureCollection", "features": []},
        "peaks": {"type": "FeatureCollection", "features": []},
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    feats = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [75.5, 35.4]},
            "properties": {
                "id": "EO_001",
                "verified": True,
                "pixel_size": 5,
                "edge_intensity": 0.5,
                "index_name": "ndmi",
            },
        }
    ]
    result = run_discovery(
        layers,
        bbox=[75.35, 35.20, 75.85, 35.55],
        discovery={"generators": {"eo_texture_anomaly": {"quota": 0}}},
        eo_scout_features=feats,
    )
    assert result["stats"]["selected_by_generator"].get("eo_texture_anomaly", 0) == 0


def test_scout_missing_raster(tmp_path: Path) -> None:
    with pytest.raises(EoAnomalyError, match="not found"):
        scout_texture_anomalies(tmp_path / "missing.tif")
