"""Pack-time VLM features (RFC-0007 / issue #22) — evidence only, never ranking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from adventure_core.config import repo_root
from adventure_core.geo import Point
from adventure_core.pack_manifest import PackManifest
from adventure_core.vlm_features import (
    VLM_FEATURES_VERSION,
    annotate_unknown_concepts,
    record_from_properties,
)
from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_data import NamedPoint, PackData, load_pack_data
from adventure_gis.vlm_join import lookup_vlm_features
from adventure_inference.models_config import load_models_config
from adventure_packbuilder.vlm import VlmBuildError, maybe_attach_vlm_features

FIXTURE = repo_root() / "fixtures" / "karakoram_mini"


def _pt(sid: str, lon: float, lat: float, **props: object) -> NamedPoint:
    return NamedPoint(id=sid, name=sid, point=Point(lon=lon, lat=lat), properties=dict(props))


def test_fixture_loads_vlm_features_into_evidence():
    data = load_pack_data(FIXTURE)
    assert len(data.vlm_features) >= 2
    cands = generate_candidates(data)
    by_id = {c.id: c for c in cands}
    pine = by_id["seed_pine_river"]
    assert pine.evidence["vlm"]["concept_ids"] == ["forest", "river", "quiet"]
    assert pine.evidence["vlm"]["vlm_version"] == VLM_FEATURES_VERSION
    assert pine.evidence["layer_flags"]["vlm_features_layer_empty"] is False
    assert by_id["seed_silent_valley"].evidence["vlm"] is None


def test_absent_vlm_layer_flag():
    pack = PackData(
        pack_dir=Path("."),
        settlements=[],
        roads=[_pt("r", 75.0, 35.5, highway="secondary")],
        water=[],
        catalog=[_pt("a", 75.0, 35.5, kind="viewpoint")],
        elevation_samples=[],
        vlm_features=[],
    )
    c = generate_candidates(pack)[0]
    assert c.evidence["vlm"] is None
    assert c.evidence["layer_flags"]["vlm_features_layer_empty"] is True


def test_lookup_exact_catalog_id_only():
    feats = [
        _pt(
            "x",
            75.001,
            35.5,
            catalog_id="seed_b",
            model="synthetic-fixture",
            concept_ids=["forest"],
            attributes={},
            prompt_id="pack_vlm_v1",
        )
    ]
    assert lookup_vlm_features("seed_a", feats) is None
    hit = lookup_vlm_features("seed_b", feats)
    assert hit is not None and hit["concept_ids"] == ["forest"]


def test_unknown_concepts_flagged_not_dropped():
    rec = record_from_properties(
        {
            "catalog_id": "c1",
            "model": "x",
            "concept_ids": ["forest", "not_a_real_concept"],
            "attributes": {},
            "prompt_id": "pack_vlm_v1",
        }
    )
    rec = annotate_unknown_concepts(rec)
    assert "forest" in rec.concept_ids
    assert "not_a_real_concept" in rec.concept_ids
    assert rec.attributes.get("unknown_concepts") == ["not_a_real_concept"]


def test_maybe_attach_disabled_clears_leftover(tmp_path: Path):
    leftover = tmp_path / "vlm_features.geojson"
    leftover.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    cfg = PackManifest(pack_id="t", name="t", bbox=[0, 0, 1, 1], vlm={"enabled": False})
    src, wrote = maybe_attach_vlm_features(cfg, tmp_path)
    assert src is None and wrote is False
    assert not leftover.exists()


def test_maybe_attach_enabled_requires_path(tmp_path: Path):
    cfg = PackManifest(pack_id="t", name="t", bbox=[0, 0, 1, 1], vlm={"enabled": True})
    with pytest.raises(VlmBuildError, match="features_geojson"):
        maybe_attach_vlm_features(cfg, tmp_path)


def test_maybe_attach_copies_and_validates(tmp_path: Path):
    src = tmp_path / "in.json"
    src.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
                        "properties": {
                            "catalog_id": "c1",
                            "concept_ids": ["lake"],
                            "attributes": {},
                        },
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
        vlm={"enabled": True, "features_geojson": str(src), "model": "llava"},
    )
    source, wrote = maybe_attach_vlm_features(cfg, layers)
    assert wrote and source is not None
    assert source.kind == "vlm"
    assert source.extra.get("role") == "features_only_not_ranking"
    out = json.loads((layers / "vlm_features.geojson").read_text(encoding="utf-8"))
    assert out["features"][0]["properties"]["vlm_version"] == VLM_FEATURES_VERSION
    assert out["features"][0]["properties"]["model"] == "llava"


def test_ranking_unchanged_with_vlm_fixture_evidence():
    from adventure_cli.pipeline import run_mission

    result = run_mission(
        prompt=(
            "Three days, Suzuki Swift, rivers and forests, hate crowds. "
            "Find a Fearless & Far style adventure."
        ),
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        interpreter="rules",
        max_results=5,
    )
    top = [m.candidate_id for m in result.missions]
    assert top == [
        "seed_pine_river",
        "seed_river_ford",
        "seed_shepherd_ruins",
        "seed_turquoise_lake",
        "seed_unnamed_tarn",
    ]
    pine = next(m for m in result.missions if m.candidate_id == "seed_pine_river")
    assert "forest" in (pine.evidence.get("vlm") or {}).get("concept_ids", [])


def test_models_yaml_pack_vlm_pin():
    cfg = load_models_config()
    assert cfg.pack_vlm
    assert "llava" in cfg.hardware_floors or cfg.pack_vlm == "llava"
