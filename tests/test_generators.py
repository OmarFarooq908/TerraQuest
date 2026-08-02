"""Unit tests for individual discovery generators (issue #5). Offline only."""

from __future__ import annotations

from adventure_core.catalog import CatalogCandidate, DensifyHook, DiscoveryConfig, Provenance
from adventure_packbuilder.discovery.context import DiscoveryContext, build_context
from adventure_packbuilder.discovery.diversity import merge_catalog_diverse, select_diverse
from adventure_packbuilder.discovery.generators import (
    gen_dem_local_max,
    gen_isolation_maximum,
    gen_named_waterbody,
    gen_osm_peak,
    gen_osm_viewpoint,
    gen_road_spur,
    gen_terrain_relief_hotspot,
    gen_track_terminus,
    gen_unnamed_waterbody,
)

BBOX = [75.35, 35.20, 75.85, 35.55]
CFG = DiscoveryConfig(min_spacing_km=0.5, grid_res_deg=0.05)


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


def _empty_layers(**overrides) -> dict:
    base = {
        "settlements": {"type": "FeatureCollection", "features": []},
        "water": {"type": "FeatureCollection", "features": []},
        "road_nodes": {"type": "FeatureCollection", "features": []},
        "road_lines": {"type": "FeatureCollection", "features": []},
        "peaks": {"type": "FeatureCollection", "features": []},
        "viewpoints": {"type": "FeatureCollection", "features": []},
    }
    base.update(overrides)
    return base


def _ctx(layers: dict) -> DiscoveryContext:
    return build_context(layers, bbox=BBOX, config=CFG, dem_paths=[])


def _cand(
    cid: str, lon: float, lat: float, *, score: float, generator: str = "x"
) -> CatalogCandidate:
    return CatalogCandidate(
        id=cid,
        name=cid,
        lon=lon,
        lat=lat,
        kind="x",
        generator=generator,
        provenance=Provenance(sources=["synthetic"], method="unit_test"),
        evidence={"discovery_score": score},
        densify=DensifyHook(cell_id=cid),
    )


def test_select_diverse_quota_zero_and_empty():
    assert select_diverse([], quota=5, min_spacing_km=1.0) == []
    c = _cand("a", 75.0, 35.0, score=1.0)
    assert select_diverse([c], quota=0, min_spacing_km=1.0) == []


def test_select_diverse_rejects_too_close_neighbors():
    # 0.001° ≈ 0.09 km; 0.05° ≈ 4.5 km at lat 35 — spacing floor 2 km.
    near = [
        _cand("hi", 75.0, 35.0, score=10.0),
        _cand("lo", 75.001, 35.0, score=9.0),
        _cand("far", 75.05, 35.0, score=8.0),
    ]
    selected = select_diverse(near, quota=3, min_spacing_km=2.0)
    assert [c.id for c in selected] == ["hi", "far"]


def test_merge_catalog_diverse_skips_near_duplicates():
    a = _cand("a", 75.0, 35.0, score=5.0, generator="named_waterbody")
    b = _cand("b", 75.0005, 35.0, score=9.0, generator="osm_peak")
    merged = merge_catalog_diverse([[a], [b]], global_min_spacing_km=1.0)
    assert len(merged) == 1
    assert merged[0].id == "b"


def test_named_vs_unnamed_waterbody_split():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        water={
            "type": "FeatureCollection",
            "features": [
                _pt(75.55, 35.35, id="w1", name="Satpara Lake", kind="lake", osm_id=1),
                _pt(75.6, 35.4, id="w2", name="unnamed_lake_2", kind="lake", osm_id=2),
            ],
        },
    )
    ctx = _ctx(layers)
    named = gen_named_waterbody(ctx)
    unnamed = gen_unnamed_waterbody(ctx)
    assert {c.generator for c in named} == {"named_waterbody"}
    assert {c.generator for c in unnamed} == {"unnamed_waterbody"}
    assert len(named) == 1 and named[0].name == "Satpara Lake"
    assert len(unnamed) == 1 and unnamed[0].name.startswith("unnamed_")
    assert all(c.has_water for c in named + unnamed)
    assert all(c.provenance.method == "water_centroid" for c in named + unnamed)
    assert named[0].evidence["ontology_ids"] == ["water.lake"]
    assert unnamed[0].evidence["ontology_ids"] == ["water.lake"]
    # Cross-contamination must not occur
    assert {c.id for c in named}.isdisjoint({c.id for c in unnamed})


def test_track_terminus_from_linestring_endpoints():
    # Settlement at Skardu; far track endpoint qualifies (~28 km), near end (~1.4 km) does not.
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        road_lines={
            "type": "FeatureCollection",
            "features": [
                _line(
                    [[75.51, 35.31], [75.72, 35.48]],
                    id="way/10",
                    highway="track",
                    osm_id=10,
                    osm_type="way",
                    name="far_spur",
                ),
            ],
        },
    )
    out = gen_track_terminus(_ctx(layers))
    assert len(out) == 1
    assert out[0].generator == "track_terminus"
    assert out[0].provenance.method == "linestring_endpoint"
    assert out[0].evidence["endpoint"] == "b"
    assert out[0].evidence["dist_settlement_km"] >= 2.5


def test_track_terminus_ignores_non_track_highways():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        road_lines={
            "type": "FeatureCollection",
            "features": [
                _line(
                    [[75.51, 35.31], [75.72, 35.48]],
                    id="way/sec",
                    highway="secondary",
                    osm_id=11,
                    osm_type="way",
                    name="main",
                ),
            ],
        },
    )
    assert gen_track_terminus(_ctx(layers)) == []


def test_track_terminus_centroid_fallback_without_lines():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        road_nodes={
            "type": "FeatureCollection",
            "features": [
                _pt(75.7, 35.45, id="r/far", highway="track", osm_id=99, name="lonely"),
                _pt(75.505, 35.302, id="r/near", highway="track", osm_id=98, name="town"),
            ],
        },
    )
    out = gen_track_terminus(_ctx(layers))
    assert len(out) == 1
    assert out[0].provenance.method == "track_centroid_fallback"
    assert out[0].evidence["endpoint"] == "centroid"
    assert "99" in out[0].id or out[0].evidence["dist_settlement_km"] >= 3.0


def test_road_spur_selects_remote_end():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        road_nodes={
            "type": "FeatureCollection",
            "features": [
                _pt(75.51, 35.31, id="r/sec", highway="secondary", osm_id=1, name="main"),
            ],
        },
        road_lines={
            "type": "FeatureCollection",
            "features": [
                _line(
                    [[75.51, 35.31], [75.72, 35.48]],
                    id="way/spur",
                    highway="track",
                    osm_id=20,
                    osm_type="way",
                    name="spur",
                ),
            ],
        },
    )
    out = gen_road_spur(_ctx(layers))
    assert len(out) == 1
    assert out[0].generator == "road_spur"
    assert out[0].evidence["far_endpoint"] == "b"
    assert out[0].lon == 75.72
    assert out[0].evidence["dist_settlement_km"] >= 3.0


def test_road_spur_rejects_unattached_track():
    # Both ends far from the drivable network → not a spur.
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        road_nodes={
            "type": "FeatureCollection",
            "features": [
                _pt(75.51, 35.31, id="r/sec", highway="secondary", osm_id=1, name="main"),
            ],
        },
        road_lines={
            "type": "FeatureCollection",
            "features": [
                _line(
                    [[75.70, 35.45], [75.72, 35.48]],
                    id="way/orphan",
                    highway="track",
                    osm_id=21,
                    osm_type="way",
                    name="orphan",
                ),
            ],
        },
    )
    assert gen_road_spur(_ctx(layers)) == []


def test_osm_peak_and_viewpoint():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.5, 35.3, name="Skardu", place="town")],
        },
        peaks={
            "type": "FeatureCollection",
            "features": [
                _pt(75.7, 35.45, id="p1", name="Peak A", osm_id=6, elevation_m=4500),
                _pt(75.71, 35.46, id="p2", name="Peak B", osm_id=8, elevation_m="bad"),
            ],
        },
        viewpoints={
            "type": "FeatureCollection",
            "features": [
                _pt(75.65, 35.42, id="v1", name="Lookout", osm_id=7),
            ],
        },
    )
    ctx = _ctx(layers)
    peaks = gen_osm_peak(ctx)
    views = gen_osm_viewpoint(ctx)
    assert len(peaks) == 2
    by_id = {c.id: c for c in peaks}
    assert by_id["gen:osm_peak:p1"].elevation_m == 4500
    assert by_id["gen:osm_peak:p2"].elevation_m is None
    assert len(views) == 1 and views[0].generator == "osm_viewpoint"
    assert views[0].provenance.method == "osm_viewpoint_node"


def test_dem_generators_empty_without_dem_paths():
    ctx = _ctx(_empty_layers())
    assert gen_dem_local_max(ctx) == []
    assert gen_terrain_relief_hotspot(ctx) == []


def test_isolation_maximum_emits_local_max_cells():
    layers = _empty_layers(
        settlements={
            "type": "FeatureCollection",
            "features": [_pt(75.4, 35.25, name="EdgeTown", place="village")],
        },
    )
    out = gen_isolation_maximum(_ctx(layers))
    assert out
    assert all(c.generator == "isolation_maximum" for c in out)
    assert all(c.evidence["dist_settlement_km"] >= 4.0 for c in out)
    assert len({c.id for c in out}) == len(out)
    again = gen_isolation_maximum(_ctx(layers))
    assert [c.id for c in out] == [c.id for c in again]


def test_isolation_maximum_empty_without_settlement_gradient():
    # Flat 999 km isolation surface → no strict local maxima.
    assert gen_isolation_maximum(_ctx(_empty_layers())) == []
