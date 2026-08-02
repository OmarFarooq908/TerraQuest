"""Fixture catalog expansion coverage (issue #6)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import get_args

from adventure_core.catalog import GeneratorName
from adventure_core.catalog_validate import validate_catalog_geojson
from adventure_core.config import repo_root
from adventure_gis.pack_data import load_pack_data

FIXTURE = repo_root() / "fixtures" / "karakoram_mini"
SHIPPING_GENERATORS = set(get_args(GeneratorName)) - {"synthetic_fixture"}
NEW_SEED_IDS = {
    "seed_unnamed_tarn",
    "seed_valley_spur",
    "seed_dem_summit",
    "seed_needle_peak",
    "seed_granite_lookout",
}


def test_fixture_catalog_covers_all_shipping_generators() -> None:
    raw = json.loads((FIXTURE / "layers" / "catalog.geojson").read_text(encoding="utf-8"))
    assert validate_catalog_geojson(raw) == []
    gens = {f["properties"]["generator"] for f in raw["features"]}
    assert gens >= SHIPPING_GENERATORS
    ids = {f["properties"]["id"] for f in raw["features"]}
    assert ids >= NEW_SEED_IDS
    assert len(raw["features"]) == 13


def test_fixture_catalog_features_marked_synthetic() -> None:
    raw = json.loads((FIXTURE / "layers" / "catalog.geojson").read_text(encoding="utf-8"))
    bbox = [74.5, 35.0, 75.5, 36.0]
    for feat in raw["features"]:
        props = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"]
        assert bbox[0] <= lon <= bbox[2]
        assert bbox[1] <= lat <= bbox[3]
        assert "synthetic" in props["provenance"]["sources"]
        assert props["provenance"]["method"] == "fixture_seed"
        assert props["evidence"].get("fixture") is True
        assert props["catalog_schema_version"] == "0.3.0"
        # Evidence ledger v1 — family keys beyond bare discovery_score
        assert "discovery_score" in props["evidence"]
        assert (
            "dist_settlement_km" in props["evidence"] or props["generator"] == "synthetic_fixture"
        )


def test_fixture_support_layers_present() -> None:
    layers = FIXTURE / "layers"
    for name in ("peaks.geojson", "viewpoints.geojson", "road_lines.geojson"):
        path = layers / name
        assert path.is_file(), name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1

    water = json.loads((layers / "water.geojson").read_text(encoding="utf-8"))
    unnamed = [
        f
        for f in water["features"]
        if not str(f["properties"].get("name") or "").strip()
        or str(f["properties"].get("name", "")).lower().startswith("unnamed")
    ]
    assert len(unnamed) >= 2

    roads = json.loads((layers / "road_nodes.geojson").read_text(encoding="utf-8"))
    assert any(f["properties"].get("highway") for f in roads["features"])


def test_fixture_pack_manifest_and_hash_check() -> None:
    from adventure_core.config import load_pack_manifest

    m, pack_dir = load_pack_manifest("fixtures/karakoram_mini")
    assert m.synthetic is True
    assert pack_dir == FIXTURE.resolve()
    data = load_pack_data(pack_dir)
    assert len(data.catalog) == 13

    script = repo_root() / "scripts" / "hash_fixture_catalog.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
