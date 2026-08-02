"""GIS feature depth: settlement density + road-class access (#23)."""

from __future__ import annotations

from pathlib import Path

from adventure_core.geo import Point
from adventure_gis.candidates import (
    _access_fit,
    _select_access_road,
    _settlement_density_kernel,
    generate_candidates,
)
from adventure_gis.pack_data import NamedPoint, PackData, load_pack_data
from adventure_scoring.confidence import build_confidence


def _pt(
    sid: str,
    lon: float,
    lat: float,
    **props: object,
) -> NamedPoint:
    return NamedPoint(
        id=sid,
        name=sid,
        point=Point(lon=lon, lat=lat),
        properties=dict(props),
    )


def test_settlement_density_empty_layer():
    dens, count = _settlement_density_kernel(Point(lon=75.0, lat=35.5), [])
    assert dens is None and count is None


def test_settlement_density_near_town_higher_than_remote():
    settlements = [
        _pt("town", 75.0, 35.5, population=50000),
        _pt("hamlet", 75.05, 35.52, population=400),
    ]
    near, n_near = _settlement_density_kernel(Point(lon=75.01, lat=35.5), settlements)
    far, n_far = _settlement_density_kernel(Point(lon=76.0, lat=36.0), settlements)
    assert near is not None and far is not None
    assert n_near is not None and n_near >= 1
    assert n_far == 0
    assert near > far
    assert 0.0 <= near <= 1.0


def test_settlement_density_handles_bad_population():
    origin = Point(lon=75.0, lat=35.5)
    dens, count = _settlement_density_kernel(origin, [_pt("s", 75.0, 35.5, population="nope")])
    assert count == 1
    assert dens is not None and dens > 0.0


def test_crowd_blends_gis_density_not_catalog_only():
    """Two seeds with identical catalog crowd props diverge when GIS density differs."""
    settlements = [
        _pt("town", 75.0, 35.5, population=80000),
    ]
    roads = [_pt("r", 75.0, 35.5, highway="secondary")]
    near = _pt("near", 75.01, 35.5, kind="viewpoint", crowd=0.1, building_density=0.1)
    far = _pt("far", 76.0, 36.0, kind="viewpoint", crowd=0.1, building_density=0.1)
    pack = PackData(
        pack_dir=Path("."),
        settlements=settlements,
        roads=roads,
        water=[],
        catalog=[near, far],
        elevation_samples=[],
    )
    by_id = {c.id: c for c in generate_candidates(pack)}
    assert by_id["near"].features.crowd > by_id["far"].features.crowd
    assert by_id["near"].features.settlement_density is not None
    assert by_id["far"].features.settlements_within_10km == 0
    assert by_id["near"].evidence["settlement_density"] == by_id["near"].features.settlement_density


def test_access_fit_penalizes_track_for_light_vehicle():
    secondary = _access_fit(4.0, "secondary", "suzuki swift", "hatchback", 3)
    track = _access_fit(4.0, "track", "suzuki swift", "hatchback", 3)
    assert secondary > track


def test_access_fit_4x4_more_tolerant_of_track():
    light_track = _access_fit(4.0, "track", "suzuki swift", "hatchback", 3)
    capable_track = _access_fit(4.0, "track", "land cruiser", "suv_4x4", 3)
    assert capable_track > light_track


def test_select_access_road_prefers_secondary_over_closer_path():
    """Sedan access must not be dominated by a footpath that happens to be nearer."""
    origin = Point(lon=75.0, lat=35.5)
    roads = [
        _pt("path", 75.004, 35.5, highway="path"),
        _pt("sec", 75.02, 35.5, highway="secondary"),
    ]
    dist, hwy = _select_access_road(
        origin, roads, vehicle="suzuki swift", vehicle_class="hatchback"
    )
    assert hwy == "secondary"
    assert dist is not None and dist > 1.0


def test_generate_candidates_records_geom_vs_access_road():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[],
        roads=[
            _pt("path", 75.004, 35.5, highway="path"),
            _pt("sec", 75.02, 35.5, highway="secondary"),
        ],
        water=[],
        catalog=[_pt("c", 75.0, 35.5, kind="viewpoint")],
        elevation_samples=[],
    )
    cand = generate_candidates(pack, vehicle="honda city", vehicle_class="sedan", days=3)[0]
    assert cand.features.nearest_highway == "secondary"
    assert cand.evidence["nearest_highway_geom"] == "path"
    assert cand.evidence["dist_road_geom_km"] is not None
    assert cand.features.dist_road_km is not None
    assert cand.features.dist_road_km > cand.evidence["dist_road_geom_km"]
    conf = build_confidence(cand)
    assert any("secondary" in r.detail for r in conf.reasons) or cand.features.access_fit < 0.4


def test_nearest_highway_on_fixture_candidates():
    pack = load_pack_data(Path("fixtures/karakoram_mini"))
    cands = generate_candidates(pack, vehicle="honda city", vehicle_class="sedan", days=3)
    assert cands
    with_hwy = [c for c in cands if c.features.nearest_highway]
    assert with_hwy, "fixture road_nodes carry highway tags"
    for c in cands:
        assert c.features.dist_road_km is None or c.features.nearest_highway is not None
        assert c.features.settlement_density is not None
        assert c.features.settlements_within_10km is not None
        assert "nearest_highway" in c.evidence
        assert "settlement_density" in c.evidence
        assert "dist_road_geom_km" in c.evidence


def test_empty_roads_nearest_highway_none():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[_pt("s", 75.2, 35.5, population=100)],
        roads=[],
        water=[],
        catalog=[_pt("c", 75.0, 35.5, kind="viewpoint")],
        elevation_samples=[],
    )
    cand = generate_candidates(pack, vehicle="honda city", days=3)[0]
    assert cand.features.nearest_highway is None
    assert cand.features.dist_road_km is None
    assert cand.features.access_fit == 0.35


def test_feature_extraction_is_deterministic():
    pack = load_pack_data(Path("fixtures/karakoram_mini"))
    a = [c.features.model_dump() for c in generate_candidates(pack, vehicle="swift", days=3)]
    b = [c.features.model_dump() for c in generate_candidates(pack, vehicle="swift", days=3)]
    assert a == b
