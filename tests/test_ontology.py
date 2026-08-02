"""Formal adventure ontology (RFC-0008) — load, validate, apply."""

from __future__ import annotations

import json

import pytest
import yaml
from adventure_core.config import repo_root
from adventure_core.intent import PREFERENCE_DIMENSIONS
from adventure_core.ontology import (
    CONCEPT_TO_DIMENSIONS,
    apply_concept,
    get_ontology,
    load_ontology,
    resolve_concept,
    validate_ontology_data,
    validate_ontology_ids,
    water_kind_to_ontology_id,
)


def test_default_ontology_loads():
    ont = get_ontology()
    assert ont.version == "1.0.0"
    assert "water.lake" in ont.concepts
    assert resolve_concept("lake") == "water.lake"
    assert resolve_concept("Lake") == "water.lake"
    assert resolve_concept("WATER.LAKE") == "water.lake"
    assert resolve_concept("water.lake") == "water.lake"
    assert resolve_concept("not_a_thing") is None


def test_concept_to_dimensions_covers_aliases_and_canonical():
    assert "lake" in CONCEPT_TO_DIMENSIONS
    assert "water.lake" in CONCEPT_TO_DIMENSIONS
    assert CONCEPT_TO_DIMENSIONS["lake"] == CONCEPT_TO_DIMENSIONS["water.lake"]
    # Legacy "vegetation" stays weaker than forest (not collapsed onto forest).
    assert CONCEPT_TO_DIMENSIONS["vegetation"] == {"forest": 0.7}
    assert CONCEPT_TO_DIMENSIONS["forest"]["forest"] == pytest.approx(0.95)
    for dims in CONCEPT_TO_DIMENSIONS.values():
        for key in dims:
            assert key in PREFERENCE_DIMENSIONS


def test_apply_concept_ignores_poisoned_module_map(monkeypatch):
    import adventure_core.ontology as ont_mod

    monkeypatch.setattr(ont_mod, "CONCEPT_TO_DIMENSIONS", {"lake": {"water": 0.01}})
    out = apply_concept({}, "lake", strength=1.0)
    assert out["water"] == pytest.approx(0.9)


def test_apply_concept_alias_and_canonical_match():
    a = apply_concept({}, "lake", strength=1.0)
    b = apply_concept({}, "water.lake", strength=1.0)
    c = apply_concept({}, "LAKE", strength=1.0)
    assert a == b == c
    assert a["water"] > 0.5


def test_validate_ontology_yaml_file():
    path = repo_root() / "configs" / "ontology" / "adventure_v1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert validate_ontology_data(data) == []
    # Round-trip through loader
    assert load_ontology().canonical_ids()


def test_invalid_preference_dimension_rejected():
    bad = {
        "ontology_version": "9.9.9",
        "concepts": {
            "water.lake": {
                "label": "Lake",
                "family": "water",
                "aliases": [],
                "preferences": {"not_a_dim": 0.5},
            }
        },
    }
    errs = validate_ontology_data(bad)
    assert any("not_a_dim" in e for e in errs)


def test_eval_fixture_ontology_ids_are_canonical():
    labels_dir = repo_root() / "evaluation" / "fixtures" / "karakoram_mini"
    seen: list[str] = []
    for path in sorted(labels_dir.glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(rows, list)
        for row in rows:
            seen.extend(row.get("ontology_ids") or [])
    assert seen, "expected ontology_ids on eval fixtures"
    assert validate_ontology_ids(seen, canonical_only=True) == []
    for oid in seen:
        assert "." in oid, oid


def test_fixture_catalog_water_evidence_ontology_ids():
    catalog = repo_root() / "fixtures" / "karakoram_mini" / "layers" / "catalog.geojson"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    water_feats = [
        f
        for f in data["features"]
        if (f.get("properties") or {}).get("generator") in {"named_waterbody", "unnamed_waterbody"}
    ]
    assert water_feats
    for feat in water_feats:
        ev = feat["properties"]["evidence"]
        ids = ev.get("ontology_ids")
        assert isinstance(ids, list) and ids
        assert validate_ontology_ids(ids, canonical_only=True) == []
        kind = ev.get("water_kind", "lake")
        assert ids[0] == water_kind_to_ontology_id(str(kind))


def test_water_kind_mapping():
    assert water_kind_to_ontology_id("lake") == "water.lake"
    assert water_kind_to_ontology_id("RIVER") == "water.river"
    assert water_kind_to_ontology_id("mystery") == "water.body"
    assert water_kind_to_ontology_id("") == "water.lake"
    assert water_kind_to_ontology_id("   ") == "water.lake"
    assert water_kind_to_ontology_id(None) == "water.lake"


def test_canonical_only_rejects_aliases():
    assert validate_ontology_ids(["lake"]) == []
    assert validate_ontology_ids(["lake"], canonical_only=True)
    assert validate_ontology_ids(["water.lake"], canonical_only=True) == []
