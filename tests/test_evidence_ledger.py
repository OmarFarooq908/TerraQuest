"""Evidence ledger v1 — required fields per generator (#19)."""

from __future__ import annotations

import pytest
from adventure_core.catalog_validate import validate_catalog_feature
from adventure_core.evidence_ledger import (
    EVIDENCE_LEDGER_VERSION,
    REQUIRED_EVIDENCE_KEYS,
    validate_evidence_ledger,
)


def test_ledger_version_and_covers_shipping_generators() -> None:
    assert EVIDENCE_LEDGER_VERSION == "1"
    assert "named_waterbody" in REQUIRED_EVIDENCE_KEYS
    assert "dem_local_max" in REQUIRED_EVIDENCE_KEYS
    assert "synthetic_fixture" in REQUIRED_EVIDENCE_KEYS


def test_missing_evidence_key_fails() -> None:
    errs = validate_evidence_ledger(
        generator="named_waterbody",
        provenance={"sources": ["osm"], "method": "water_centroid", "layer": "water"},
        evidence={"discovery_score": 0.5, "dist_settlement_km": 3.0},
        feature_id="w1",
    )
    assert any("water_kind" in e for e in errs)
    assert any("named" in e for e in errs)


def test_synthetic_requires_fixture_flag() -> None:
    errs = validate_evidence_ledger(
        generator="isolation_maximum",
        provenance={"sources": ["synthetic"], "method": "fixture_seed", "layer": "settlements"},
        evidence={
            "discovery_score": 0.8,
            "dist_settlement_km": 12.0,
            "grid_res_deg": 0.02,
        },
        feature_id="i1",
    )
    assert any("fixture=true" in e for e in errs)


def test_osm_generator_requires_osm_source() -> None:
    errs = validate_evidence_ledger(
        generator="osm_peak",
        provenance={"sources": ["dem"], "method": "osm_peak_node", "layer": "peaks"},
        evidence={"discovery_score": 0.5, "dist_settlement_km": 4.0},
        feature_id="p1",
    )
    assert any("'osm'" in e for e in errs)


def test_dem_requires_dem_tile_when_real() -> None:
    errs = validate_evidence_ledger(
        generator="dem_local_max",
        provenance={"sources": ["dem"], "method": "dem_grid_local_max"},
        evidence={
            "discovery_score": 0.5,
            "dist_settlement_km": 4.0,
            "elevation_m": 4000.0,
        },
        feature_id="d1",
    )
    assert any("dem_tile" in e for e in errs)


def test_happy_path_real_water() -> None:
    errs = validate_evidence_ledger(
        generator="named_waterbody",
        provenance={
            "sources": ["osm"],
            "method": "water_centroid",
            "layer": "water",
            "osm_id": 1,
        },
        evidence={
            "discovery_score": 0.7,
            "dist_settlement_km": 5.0,
            "water_kind": "lake",
            "named": True,
        },
        feature_id="w2",
    )
    assert errs == []


def test_unknown_generator_and_empty_sources() -> None:
    assert any(
        "unknown generator" in e
        for e in validate_evidence_ledger(
            generator="not_a_real_gen",
            provenance={"sources": ["osm"], "method": "x"},
            evidence={},
            feature_id="u1",
        )
    )
    assert any(
        "non-empty list" in e
        for e in validate_evidence_ledger(
            generator="named_waterbody",
            provenance={"sources": [], "method": "water_centroid", "layer": "water"},
            evidence={
                "discovery_score": 0.5,
                "dist_settlement_km": 1.0,
                "water_kind": "lake",
                "named": True,
            },
            feature_id="u2",
        )
    )


def test_empty_generator_does_not_bypass_ledger() -> None:
    feat = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [75.0, 35.5]},
        "properties": {
            "id": "blank_gen",
            "name": "Blank",
            "generator": "",
            "provenance": {"sources": ["osm"], "method": "x", "layer": "water"},
            "evidence": {},
            "densify": {
                "cell_id": "c",
                "parent_id": None,
                "densify_allowed": True,
                "grid_res_deg": 0.02,
            },
        },
    }
    errs = validate_catalog_feature(feat, index=0)
    assert any("non-empty string" in e for e in errs)


def test_empty_string_evidence_values_rejected() -> None:
    errs = validate_evidence_ledger(
        generator="named_waterbody",
        provenance={"sources": ["osm"], "method": "water_centroid", "layer": "water"},
        evidence={
            "discovery_score": 0.5,
            "dist_settlement_km": 2.0,
            "water_kind": "  ",
            "named": True,
        },
        feature_id="w_empty",
    )
    assert any("water_kind" in e for e in errs)


def test_named_false_is_allowed_for_unnamed_water() -> None:
    errs = validate_evidence_ledger(
        generator="unnamed_waterbody",
        provenance={"sources": ["osm"], "method": "water_centroid", "layer": "water"},
        evidence={
            "discovery_score": 0.5,
            "dist_settlement_km": 2.0,
            "water_kind": "lake",
            "named": False,
        },
        feature_id="uw1",
    )
    assert errs == []


def test_synthetic_fixture_requires_fixture_even_without_synthetic_source() -> None:
    errs = validate_evidence_ledger(
        generator="synthetic_fixture",
        provenance={"sources": ["osm"], "method": "unit_test", "layer": "catalog"},
        evidence={"discovery_score": 0.5},
        feature_id="sf1",
    )
    assert any("fixture=true" in e for e in errs)


def test_required_keys_cover_shipping_generators() -> None:
    from adventure_core.evidence_ledger import REQUIRED_EVIDENCE_KEYS, shipping_generator_names
    from adventure_packbuilder.discovery.generators import GENERATORS

    shipping = shipping_generator_names()
    assert set(GENERATORS) == shipping
    assert shipping <= set(REQUIRED_EVIDENCE_KEYS)
    assert "synthetic_fixture" in REQUIRED_EVIDENCE_KEYS


def test_dem_generator_outputs_satisfy_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from adventure_core.catalog import DiscoveryConfig
    from adventure_packbuilder.discovery.context import build_context
    from adventure_packbuilder.discovery.generators import (
        gen_dem_local_max,
        gen_terrain_relief_hotspot,
    )

    def pt(lon: float, lat: float, **props):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        }

    layers = {
        "settlements": {
            "type": "FeatureCollection",
            "features": [pt(75.5, 35.3, name="Skardu", place="town")],
        },
        "water": {"type": "FeatureCollection", "features": []},
        "road_nodes": {"type": "FeatureCollection", "features": []},
        "road_lines": {"type": "FeatureCollection", "features": []},
        "peaks": {"type": "FeatureCollection", "features": []},
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    dem = tmp_path / "N35E075.tif"
    dem.write_bytes(b"fake")
    ctx = build_context(
        layers,
        bbox=[75.35, 35.20, 75.85, 35.55],
        config=DiscoveryConfig(min_spacing_km=0.5, grid_res_deg=0.05),
        dem_paths=[dem],
    )

    def fake_elevs(coords, _paths):
        # Peak at first grid point far enough from town
        out = []
        for lon, lat in coords:
            # Higher toward NE corner → local max pattern
            out.append(3000.0 + (lon - 75.35) * 2000 + (lat - 35.20) * 1500)
        return out

    def fake_relief(lon, lat, _paths, radius_deg=0.05):
        return 800.0 if lon > 75.6 else 100.0

    monkeypatch.setattr(
        "adventure_packbuilder.discovery.generators.sample_elevations",
        fake_elevs,
    )
    monkeypatch.setattr(
        "adventure_packbuilder.discovery.generators.local_relief_from_dem",
        fake_relief,
    )

    dem_cands = gen_dem_local_max(ctx)
    relief_cands = gen_terrain_relief_hotspot(ctx)
    assert dem_cands or relief_cands
    for cand in dem_cands + relief_cands:
        errs = validate_evidence_ledger(
            generator=cand.generator,
            provenance=cand.provenance.model_dump(),
            evidence=cand.evidence,
            feature_id=cand.id,
        )
        assert errs == [], (cand.generator, cand.id, errs)


def test_dem_source_and_osm_layer_required() -> None:
    dem_src = validate_evidence_ledger(
        generator="terrain_relief_hotspot",
        provenance={"sources": ["osm"], "method": "dem_local_relief_window", "dem_tile": "t.tif"},
        evidence={
            "discovery_score": 0.5,
            "dist_settlement_km": 4.0,
            "relief_m": 500.0,
        },
        feature_id="r1",
    )
    assert any("'dem'" in e for e in dem_src)

    no_layer = validate_evidence_ledger(
        generator="named_waterbody",
        provenance={"sources": ["osm"], "method": "water_centroid"},
        evidence={
            "discovery_score": 0.5,
            "dist_settlement_km": 1.0,
            "water_kind": "lake",
            "named": True,
        },
        feature_id="w3",
    )
    assert any("layer required" in e for e in no_layer)


def test_catalog_feature_enforces_ledger() -> None:
    feat = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [75.0, 35.5]},
        "properties": {
            "id": "bad_water",
            "name": "Bad",
            "generator": "named_waterbody",
            "provenance": {"sources": ["osm"], "method": "water_centroid", "layer": "water"},
            "evidence": {"discovery_score": 0.1},
            "densify": {
                "cell_id": "c",
                "parent_id": None,
                "densify_allowed": True,
                "grid_res_deg": 0.02,
            },
        },
    }
    errs = validate_catalog_feature(feat, index=0)
    assert any("evidence missing" in e for e in errs)


def test_generator_outputs_satisfy_ledger() -> None:
    """Packbuilder shipping generators already emit ledger-complete evidence."""
    from adventure_core.catalog import DiscoveryConfig
    from adventure_packbuilder.discovery.context import build_context
    from adventure_packbuilder.discovery.generators import (
        gen_isolation_maximum,
        gen_named_waterbody,
        gen_osm_peak,
        gen_osm_viewpoint,
        gen_road_spur,
        gen_track_terminus,
        gen_unnamed_waterbody,
    )

    def pt(lon: float, lat: float, **props):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        }

    def line(coords, **props):
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props,
        }

    layers = {
        "settlements": {
            "type": "FeatureCollection",
            "features": [pt(75.5, 35.3, name="Skardu", place="town")],
        },
        "water": {
            "type": "FeatureCollection",
            "features": [
                pt(75.55, 35.35, id="w1", name="Satpara Lake", kind="lake", osm_id=1),
                pt(75.6, 35.4, id="w2", name="unnamed_lake_2", kind="lake", osm_id=2),
            ],
        },
        "road_nodes": {
            "type": "FeatureCollection",
            "features": [pt(75.51, 35.31, highway="secondary", osm_id=3)],
        },
        "road_lines": {
            "type": "FeatureCollection",
            "features": [
                line(
                    [[75.51, 35.31], [75.72, 35.48]],
                    id="way/10",
                    highway="track",
                    osm_id=10,
                    osm_type="way",
                    name="far_spur",
                ),
            ],
        },
        "peaks": {
            "type": "FeatureCollection",
            "features": [pt(75.7, 35.5, name="Peak", ele=4200, osm_id=21)],
        },
        "viewpoints": {
            "type": "FeatureCollection",
            "features": [pt(75.65, 35.45, name="VP", osm_id=22)],
        },
    }
    ctx = build_context(
        layers,
        bbox=[75.35, 35.20, 75.85, 35.55],
        config=DiscoveryConfig(min_spacing_km=0.5, grid_res_deg=0.05),
        dem_paths=[],
    )
    produced = (
        gen_named_waterbody(ctx)
        + gen_unnamed_waterbody(ctx)
        + gen_track_terminus(ctx)
        + gen_road_spur(ctx)
        + gen_osm_peak(ctx)
        + gen_osm_viewpoint(ctx)
        + gen_isolation_maximum(ctx)
    )
    assert produced
    for cand in produced:
        errs = validate_evidence_ledger(
            generator=cand.generator,
            provenance=cand.provenance.model_dump(),
            evidence=cand.evidence,
            feature_id=cand.id,
        )
        assert errs == [], (cand.generator, cand.id, errs)
