"""Remoteness / distance feature edge cases (issue #30)."""

from __future__ import annotations

from pathlib import Path

import pytest
from adventure_core.geo import Point
from adventure_core.schemas import CandidateFeatures
from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_data import NamedPoint, PackData, load_pack_data
from adventure_scoring.confidence import build_confidence
from pydantic import ValidationError


def _seed(
    sid: str = "t1",
    *,
    lon: float = 75.0,
    lat: float = 35.5,
    **props: object,
) -> NamedPoint:
    base = {
        "kind": "viewpoint",
        "generator": "synthetic_fixture",
        "building_density": 0.1,
        "crowd": 0.1,
    }
    base.update(props)
    return NamedPoint(id=sid, name=sid, point=Point(lon=lon, lat=lat), properties=base)


def test_candidate_features_reject_out_of_range_remoteness():
    with pytest.raises(ValidationError):
        CandidateFeatures(
            remoteness=-1.0,
            terrain_drama=0.1,
            water=0.1,
            viewpoint=0.1,
            novelty=0.1,
            access_fit=0.1,
            camping=0.1,
            forest=0.1,
            crowd=0.1,
            risk=0.1,
            restriction=0.0,
        )


def test_empty_settlements_no_999_sentinel():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[],
        roads=[_seed("r1", lon=75.01, lat=35.5)],
        water=[],
        catalog=[_seed("c1")],
        elevation_samples=[],
    )
    cand = generate_candidates(pack)[0]
    assert cand.features.dist_settlement_km is None
    assert cand.features.remoteness == 0.5
    assert cand.evidence["layer_flags"]["settlements_layer_empty"] is True
    conf = build_confidence(cand)
    assert "settlements_layer_missing" in conf.uncertainties
    assert not any("999" in r.detail for r in conf.reasons)


def test_empty_roads_access_is_neutral_not_fake_far():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[_seed("s1", lon=75.2, lat=35.5)],
        roads=[],
        water=[],
        catalog=[_seed("c1")],
        elevation_samples=[],
    )
    cand = generate_candidates(pack, vehicle="honda city", days=3)[0]
    assert cand.features.dist_road_km is None
    assert 0.0 <= cand.features.access_fit <= 1.0
    assert cand.evidence["layer_flags"]["roads_layer_empty"] is True


def test_coincident_settlement_remoteness_zero():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[_seed("s1", lon=75.0, lat=35.5)],
        roads=[_seed("r1", lon=75.0, lat=35.5)],
        water=[],
        catalog=[_seed("c1", lon=75.0, lat=35.5)],
        elevation_samples=[],
    )
    cand = generate_candidates(pack)[0]
    assert cand.features.dist_settlement_km == 0.0
    assert cand.features.remoteness == 0.0


def test_bad_property_values_clamped():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[_seed("s1", lon=74.0, lat=35.0)],
        roads=[_seed("r1", lon=75.01, lat=35.5)],
        water=[],
        catalog=[
            _seed(
                "c1",
                building_density=9.0,
                crowd=-3.0,
                forest="nan",
                hazard="inf",
                slope=-1.0,
            )
        ],
        elevation_samples=[],
    )
    cand = generate_candidates(pack)[0]
    f = cand.features
    for name in (
        "remoteness",
        "terrain_drama",
        "water",
        "viewpoint",
        "novelty",
        "access_fit",
        "camping",
        "forest",
        "crowd",
        "risk",
        "restriction",
    ):
        v = getattr(f, name)
        assert 0.0 <= v <= 1.0, name


def test_fixture_pack_features_in_unit_interval():
    pack = load_pack_data(Path("fixtures/karakoram_mini"))
    cands = generate_candidates(pack, vehicle="suzuki swift", days=3)
    assert cands
    for cand in cands:
        f = cand.features
        assert 0.0 <= f.remoteness <= 1.0
        assert f.dist_settlement_km is None or f.dist_settlement_km >= 0.0
        assert f.dist_settlement_km != 999.0
        conf = build_confidence(cand)
        assert 0.05 <= conf.value <= 0.92
