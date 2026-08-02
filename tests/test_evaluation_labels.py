"""CI gates for evaluation place-label JSON (RFC-0002 / issue #56)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from adventure_core.config import repo_root
from adventure_core.evaluation import (
    load_place_labels,
    place_label_json_files,
    validate_place_label_corpus,
)

EVAL_ROOT = repo_root() / "evaluation"
SKARDU = EVAL_ROOT / "skardu"
FIXTURES = EVAL_ROOT / "fixtures" / "karakoram_mini"


def test_evaluation_corpus_valid():
    errors = validate_place_label_corpus(EVAL_ROOT)
    assert errors == [], "\n".join(errors)


def test_place_label_files_skip_schema_and_reports():
    files = place_label_json_files(EVAL_ROOT)
    assert files
    assert all("schema" not in p.parts for p in files)
    assert all("reports" not in p.parts for p in files)
    assert (EVAL_ROOT / "schema" / "place_label.schema.json").is_file()


def test_skardu_seed_meets_minimum_counts():
    labels = load_place_labels(SKARDU)
    interesting = [lb for lb in labels if lb.interesting]
    controls = [
        lb
        for lb in labels
        if (not lb.interesting)
        or (lb.google_maps_popularity is not None and lb.google_maps_popularity >= 7.0)
    ]
    assert len(interesting) >= 10
    assert len(controls) >= 5
    assert all(not lb.synthetic for lb in labels)
    assert all(lb.license for lb in labels)


def test_skardu_opposite_interesting_pairs_beyond_two_match_radii():
    """Distance matching is nearest-within-radius; midpoints must not flip polarity."""
    from adventure_core.evaluation import NORTH_STAR_MATCH_RADIUS_KM
    from adventure_core.geo import haversine_km

    labels = load_place_labels(SKARDU)
    min_km = 2.0 * NORTH_STAR_MATCH_RADIUS_KM
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            if a.interesting == b.interesting:
                continue
            d = haversine_km(a.geometry.as_point(), b.geometry.as_point())
            assert d > min_km, f"{a.id} vs {b.id}: {d:.2f} km ≤ {min_km}"


def test_place_label_forbids_unknown_fields():
    from adventure_core.evaluation import PlaceLabel
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlaceLabel.model_validate(
            {
                "schema_version": "0.1.0",
                "id": "x",
                "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
                "known": True,
                "interesting": True,
                "license": "Apache-2.0",
                "synthetic": True,
                "not_in_schema": True,
            }
        )


def test_corpus_rejects_duplicate_catalog_id(tmp_path: Path):
    root = tmp_path / "evaluation"
    (root / "schema").mkdir(parents=True)
    (root / "schema" / "place_label.schema.json").write_text(
        (EVAL_ROOT / "schema" / "place_label.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "fixtures" / "mini").mkdir(parents=True)
    rows = [
        {
            "schema_version": "0.1.0",
            "id": "fixtures/mini/a",
            "catalog_id": "dup",
            "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
            "known": True,
            "interesting": True,
            "license": "Apache-2.0",
            "synthetic": True,
        },
        {
            "schema_version": "0.1.0",
            "id": "fixtures/mini/b",
            "catalog_id": "dup",
            "geometry": {"type": "Point", "coordinates": [75.1, 35.1]},
            "known": True,
            "interesting": True,
            "license": "Apache-2.0",
            "synthetic": True,
        },
    ]
    (root / "fixtures" / "mini" / "x.json").write_text(json.dumps(rows), encoding="utf-8")
    errors = validate_place_label_corpus(root)
    assert any("duplicate catalog_id" in e for e in errors)


def test_corpus_rejects_opposite_interesting_too_close(tmp_path: Path):
    root = tmp_path / "evaluation"
    (root / "schema").mkdir(parents=True)
    (root / "schema" / "place_label.schema.json").write_text(
        (EVAL_ROOT / "schema" / "place_label.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "skardu").mkdir()
    rows = [
        {
            "schema_version": "0.1.0",
            "id": "skardu/a",
            "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
            "known": True,
            "interesting": True,
            "license": "CC-BY-4.0",
            "synthetic": False,
        },
        {
            "schema_version": "0.1.0",
            "id": "skardu/b",
            "geometry": {"type": "Point", "coordinates": [75.01, 35.0]},
            "known": True,
            "interesting": False,
            "license": "CC-BY-4.0",
            "synthetic": False,
        },
    ]
    (root / "skardu" / "close.json").write_text(json.dumps(rows), encoding="utf-8")
    errors = validate_place_label_corpus(root)
    assert any("opposite-interesting" in e for e in errors)


def test_fixture_labels_remain_synthetic():
    labels = load_place_labels(FIXTURES)
    assert labels
    assert all(lb.synthetic for lb in labels)


def test_json_schema_required_keys_match_pydantic_roundtrip():
    schema = json.loads(
        (EVAL_ROOT / "schema" / "place_label.schema.json").read_text(encoding="utf-8")
    )
    required = set(schema["required"])
    sample = load_place_labels(FIXTURES)[0]
    dumped = json.loads(sample.model_dump_json())
    assert required <= set(dumped.keys())


def test_corpus_rejects_bad_ontology_id(tmp_path: Path):
    root = tmp_path / "evaluation"
    (root / "schema").mkdir(parents=True)
    (root / "schema" / "place_label.schema.json").write_text(
        (EVAL_ROOT / "schema" / "place_label.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "skardu").mkdir()
    bad = [
        {
            "schema_version": "0.1.0",
            "id": "skardu/test/bad_oid",
            "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
            "known": True,
            "interesting": True,
            "license": "CC-BY-4.0",
            "synthetic": False,
            "ontology_ids": ["not.a.real.concept"],
        }
    ]
    (root / "skardu" / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    errors = validate_place_label_corpus(root)
    assert any("unknown ontology id" in e for e in errors)


def test_corpus_rejects_fixture_marked_non_synthetic(tmp_path: Path):
    root = tmp_path / "evaluation"
    (root / "schema").mkdir(parents=True)
    (root / "schema" / "place_label.schema.json").write_text(
        (EVAL_ROOT / "schema" / "place_label.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "fixtures" / "mini").mkdir(parents=True)
    row = {
        "schema_version": "0.1.0",
        "id": "fixtures/mini/x",
        "geometry": {"type": "Point", "coordinates": [75.0, 35.0]},
        "known": True,
        "interesting": True,
        "license": "Apache-2.0",
        "synthetic": False,
    }
    (root / "fixtures" / "mini" / "x.json").write_text(json.dumps([row]), encoding="utf-8")
    errors = validate_place_label_corpus(root)
    assert any("synthetic=true" in e for e in errors)
