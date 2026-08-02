"""Strict catalog.geojson validation (issue #13)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from adventure_core.catalog_validate import (
    CatalogValidationError,
    validate_catalog_feature,
    validate_catalog_geojson,
)
from adventure_core.config import repo_root
from adventure_gis import load_pack_data, validate_pack

FIXTURE = repo_root() / "fixtures" / "karakoram_mini"


def _minimal_feature(**prop_overrides) -> dict:
    props = {
        "id": "c1",
        "name": "Test Place",
        "kind": "place",
        "generator": "synthetic_fixture",
        "generator_version": "1",
        "catalog_schema_version": "0.3.0",
        "provenance": {"sources": ["synthetic"], "method": "unit_test", "layer": "catalog"},
        "evidence": {"discovery_score": 0.5, "fixture": True},
        "densify": {
            "cell_id": "c_0_0",
            "parent_id": None,
            "densify_allowed": True,
            "grid_res_deg": 0.02,
        },
    }
    props.update(prop_overrides)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [75.0, 35.5]},
        "properties": props,
    }


def test_fixture_catalog_validates():
    raw = json.loads((FIXTURE / "layers" / "catalog.geojson").read_text(encoding="utf-8"))
    assert validate_catalog_geojson(raw) == []


def test_check_pack_fixture_passes():
    assert validate_pack("fixtures/karakoram_mini") == []


def test_load_pack_data_fixture():
    data = load_pack_data(FIXTURE)
    assert len(data.catalog) == 13
    generators = {c.properties.get("generator") for c in data.catalog}
    assert generators >= {
        "named_waterbody",
        "unnamed_waterbody",
        "isolation_maximum",
        "terrain_relief_hotspot",
        "track_terminus",
        "road_spur",
        "dem_local_max",
        "osm_peak",
        "osm_viewpoint",
    }


def test_missing_required_property():
    feat = _minimal_feature()
    del feat["properties"]["provenance"]
    errs = validate_catalog_feature(feat, index=0)
    assert any("provenance" in e for e in errs)


def test_bad_geometry():
    feat = _minimal_feature()
    feat["geometry"] = {"type": "Point", "coordinates": [200.0, 35.0]}
    errs = validate_catalog_feature(feat, index=0)
    assert any("out of range" in e for e in errs)


def test_empty_collection():
    errs = validate_catalog_geojson({"type": "FeatureCollection", "features": []})
    assert any("empty" in e for e in errs)


def test_geometry_edge_cases():
    feat = _minimal_feature()
    feat["geometry"] = "not-an-object"
    assert any("geometry" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature()
    feat["geometry"] = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
    assert any("Point" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature()
    feat["geometry"] = {"type": "Point", "coordinates": [75.0]}
    assert any("coordinates" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature()
    feat["geometry"] = {"type": "Point", "coordinates": ["x", "y"]}
    assert any("invalid coordinates" in e for e in validate_catalog_feature(feat, index=0))


def test_feature_shape_errors():
    assert validate_catalog_feature("x", index=3) == ["features[3]: not an object"]  # type: ignore[arg-type]
    feat = _minimal_feature()
    feat["type"] = "NotFeature"
    assert any("Feature" in e for e in validate_catalog_feature(feat, index=0))
    feat = _minimal_feature()
    feat["properties"] = None
    assert any("properties" in e for e in validate_catalog_feature(feat, index=0))


def test_schema_version_and_provenance_types():
    feat = _minimal_feature(catalog_schema_version="9.9.9")
    assert any("catalog_schema_version" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature(provenance="bad")
    assert any("provenance" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature(provenance={"sources": "synthetic", "method": "x"})
    errs = validate_catalog_feature(feat, index=0)
    assert errs and any("schema" in e or "sources" in e or "list" in e for e in errs)

    feat = _minimal_feature(provenance={"sources": [], "method": ""})
    assert any("method" in e for e in validate_catalog_feature(feat, index=0))

    feat = _minimal_feature(evidence=[])
    assert any("evidence" in e for e in validate_catalog_feature(feat, index=0))


def test_root_document_errors():
    assert validate_catalog_geojson([]) == ["catalog root must be an object"]  # type: ignore[arg-type]
    errs = validate_catalog_geojson({"type": "Feature", "features": []})
    assert any("FeatureCollection" in e for e in errs)
    assert any(
        "features must be a list" in e
        for e in validate_catalog_geojson({"type": "FeatureCollection"})
    )


def test_dual_path_rejected(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    shutil.copy(dest / "layers" / "catalog.geojson", dest / "layers" / "seeds.geojson")
    errs = validate_pack(str(dest))
    assert any("dual-path" in e for e in errs)


def test_dual_path_allowed_with_flag(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    shutil.copy(dest / "layers" / "catalog.geojson", dest / "layers" / "seeds.geojson")
    errs = validate_pack(str(dest), allow_legacy_seeds=True)
    assert not any("dual-path" in e for e in errs)


def test_invalid_catalog_fails_check_pack(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    catalog = dest / "layers" / "catalog.geojson"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    del data["features"][0]["properties"]["generator"]
    catalog.write_text(json.dumps(data), encoding="utf-8")
    errs = validate_pack(str(dest))
    assert any("generator" in e for e in errs)


def test_load_pack_data_refuses_invalid(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    catalog = dest / "layers" / "catalog.geojson"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    del data["features"][0]["properties"]["evidence"]
    catalog.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CatalogValidationError, match="evidence"):
        load_pack_data(dest)


def test_content_hash_requires_build_stats(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8")
    pack_yaml.write_text(text + "\ncontent_hash: deadbeefdeadbeef\n", encoding="utf-8")
    errs = validate_pack(str(dest))
    assert any("build_stats.json is missing" in e for e in errs)


def test_content_hash_mismatch(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8")
    pack_yaml.write_text(text + "\ncontent_hash: deadbeefdeadbeef\n", encoding="utf-8")
    (dest / "build_stats.json").write_text(
        json.dumps({"discovery": {"selected_by_generator": {}}}),
        encoding="utf-8",
    )
    errs = validate_pack(str(dest))
    assert any("content_hash mismatch" in e for e in errs)


def test_seeds_only_with_allow_flag(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    catalog = dest / "layers" / "catalog.geojson"
    seeds = dest / "layers" / "seeds.geojson"
    catalog.rename(seeds)
    with pytest.warns(DeprecationWarning):
        errs = validate_pack(str(dest), allow_legacy_seeds=True)
    assert errs == []


def test_seeds_only_without_allow_flag(tmp_path: Path):
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    catalog = dest / "layers" / "catalog.geojson"
    catalog.rename(dest / "layers" / "seeds.geojson")
    errs = validate_pack(str(dest))
    assert any("missing" in e and "catalog.geojson" in e for e in errs)


def test_cli_check_pack_exit_codes():
    from subprocess import run

    ok = run(
        [sys.executable, str(repo_root() / "scripts" / "check_pack.py"), "fixtures/karakoram_mini"],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0
    assert '"ok": true' in ok.stdout
