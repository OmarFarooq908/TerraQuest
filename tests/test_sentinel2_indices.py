"""Sentinel-2 optional index layer + featurize path (RFC-0006 / issue #21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from adventure_core.config import repo_root
from adventure_core.geo import Point
from adventure_core.pack_manifest import PackManifest
from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_data import NamedPoint, PackData, load_pack_data
from adventure_gis.sentinel import lookup_sentinel_indices
from adventure_packbuilder.sentinel2 import Sentinel2BuildError, maybe_attach_sentinel_indices

FIXTURE = repo_root() / "fixtures" / "karakoram_mini"


def _pt(sid: str, lon: float, lat: float, **props: object) -> NamedPoint:
    return NamedPoint(id=sid, name=sid, point=Point(lon=lon, lat=lat), properties=dict(props))


def test_fixture_loads_sentinel_indices():
    data = load_pack_data(FIXTURE)
    assert len(data.sentinel_indices) >= 3
    cands = generate_candidates(data)
    by_id = {c.id: c for c in cands}
    assert by_id["seed_turquoise_lake"].features.ndwi == pytest.approx(0.55)
    assert by_id["seed_pine_river"].features.ndvi == pytest.approx(0.72)
    assert (
        by_id["seed_turquoise_lake"].evidence["layer_flags"]["sentinel_indices_layer_empty"]
        is False
    )
    assert by_id["seed_silent_valley"].features.ndvi is None  # not in synthetic layer
    assert by_id["seed_silent_valley"].evidence["sentinel"] is None


def test_absent_sentinel_layer_features_null():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[],
        roads=[_pt("r", 75.0, 35.5, highway="secondary")],
        water=[],
        catalog=[_pt("a", 75.0, 35.5, kind="viewpoint")],
        elevation_samples=[],
        sentinel_indices=[],
    )
    c = generate_candidates(pack)[0]
    assert c.features.ndvi is None and c.features.ndwi is None
    assert c.evidence["layer_flags"]["sentinel_indices_layer_empty"] is True


def test_lookup_prefers_catalog_id_over_nearby_point():
    indices = [
        _pt("wrong", 75.0, 35.5, catalog_id="other", ndvi=0.1, ndwi=0.1),
        _pt("right", 75.1, 35.6, catalog_id="seed_a", ndvi=0.8, ndwi=0.2),
    ]
    ndvi, ndwi, meta = lookup_sentinel_indices("seed_a", Point(lon=75.0, lat=35.5), indices)
    assert ndvi == pytest.approx(0.8)
    assert ndwi == pytest.approx(0.2)
    assert meta["match_via"] == "catalog_id"


def test_lookup_distance_fallback():
    indices = [_pt("near", 75.001, 35.5, ndvi=0.4, ndwi=0.1)]  # no catalog_id
    ndvi, _, meta = lookup_sentinel_indices("seed_x", Point(lon=75.0, lat=35.5), indices)
    assert ndvi == pytest.approx(0.4)
    assert meta["match_via"] == "distance"


def test_lookup_does_not_steal_neighbor_catalog_id():
    """Dense catalogs: unlabeled seed must not inherit a nearby labeled sample."""
    indices = [
        _pt("b_idx", 75.001, 35.5, catalog_id="seed_b", ndvi=0.9, ndwi=0.1),
    ]
    ndvi_a, _, meta_a = lookup_sentinel_indices("seed_a", Point(lon=75.0, lat=35.5), indices)
    ndvi_b, _, meta_b = lookup_sentinel_indices("seed_b", Point(lon=75.001, lat=35.5), indices)
    assert ndvi_a is None and meta_a == {}
    assert ndvi_b == pytest.approx(0.9)
    assert meta_b["match_via"] == "catalog_id"


def test_optional_index_rejects_non_finite():
    indices = [_pt("x", 75.0, 35.5, catalog_id="c1", ndvi=float("nan"), ndwi=float("inf"))]
    ndvi, ndwi, meta = lookup_sentinel_indices("c1", Point(lon=75.0, lat=35.5), indices)
    assert ndvi is None and ndwi is None
    assert meta["match_via"] == "catalog_id"


def test_maybe_attach_disabled_clears_leftover_layer(tmp_path: Path):
    leftover = tmp_path / "sentinel_indices.geojson"
    leftover.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": False},
    )
    src, wrote = maybe_attach_sentinel_indices(cfg, tmp_path)
    assert src is None and wrote is False
    assert not leftover.exists()


def test_maybe_attach_rejects_empty_and_duplicate(tmp_path: Path):
    empty = tmp_path / "empty.json"
    empty.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    layers = tmp_path / "layers"
    layers.mkdir()
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": True, "indices_geojson": str(empty)},
    )
    with pytest.raises(Sentinel2BuildError, match="empty"):
        maybe_attach_sentinel_indices(cfg, layers)

    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
                        "properties": {"catalog_id": "c1", "ndvi": 0.1},
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [75.1, 35.1]},
                        "properties": {"catalog_id": "c1", "ndvi": 0.2},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    cfg2 = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": True, "indices_geojson": str(dup)},
    )
    with pytest.raises(Sentinel2BuildError, match="duplicate"):
        maybe_attach_sentinel_indices(cfg2, layers)


def test_maybe_attach_rejects_bad_coordinates(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [999.0, 35.0]},
                        "properties": {"catalog_id": "c1", "ndvi": 0.1},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    layers = tmp_path / "layers"
    layers.mkdir()
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": True, "indices_geojson": str(bad)},
    )
    with pytest.raises(Sentinel2BuildError, match="WGS84"):
        maybe_attach_sentinel_indices(cfg, layers)


def test_maybe_attach_disabled_is_noop(tmp_path: Path):
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": False},
    )
    src, wrote = maybe_attach_sentinel_indices(cfg, tmp_path)
    assert src is None and wrote is False
    assert not (tmp_path / "sentinel_indices.geojson").exists()


def test_maybe_attach_enabled_without_path_fails(tmp_path: Path):
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": True},
    )
    with pytest.raises(Sentinel2BuildError, match="indices_geojson"):
        maybe_attach_sentinel_indices(cfg, tmp_path)


def test_maybe_attach_copies_normalized_layer(tmp_path: Path):
    src = tmp_path / "in.json"
    src.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
                        "properties": {"catalog_id": "c1", "ndvi": 0.5, "ndwi": 0.1},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    layers = tmp_path / "layers"
    layers.mkdir()
    cfg = PackManifest(
        pack_id="t",
        name="t",
        bbox=[0, 0, 1, 1],
        sentinel2={"enabled": True, "indices_geojson": str(src)},
    )
    source, wrote = maybe_attach_sentinel_indices(cfg, layers)
    assert wrote and source is not None
    assert source.kind == "sentinel2"
    out = json.loads((layers / "sentinel_indices.geojson").read_text(encoding="utf-8"))
    assert out["features"][0]["properties"]["index_version"] == "s2-indices-v1"


def test_ranking_unchanged_with_sentinel_fixture_features():
    """RFC-0006: indices populate features but do not change preference ranking yet."""
    from adventure_cli.pipeline import run_mission

    prompt = (
        "Three days, Suzuki Swift, rivers and forests, hate crowds. "
        "Find a Fearless & Far style adventure."
    )
    result = run_mission(
        prompt=prompt,
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        interpreter="rules",
        max_results=5,
    )
    top = [m.candidate_id for m in result.missions]
    # Pinned baseline top ids (evaluation/reports/karakoram_mini_baseline.md)
    assert top == [
        "seed_pine_river",
        "seed_river_ford",
        "seed_shepherd_ruins",
        "seed_turquoise_lake",
        "seed_unnamed_tarn",
    ]
    pine = next(m for m in result.missions if m.candidate_id == "seed_pine_river")
    assert pine.evidence.get("ndvi") == pytest.approx(0.72)
