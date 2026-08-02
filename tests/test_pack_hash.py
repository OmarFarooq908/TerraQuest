"""Pack content hash + contract validation (RFC-0003 / issue #18)."""

from __future__ import annotations

import shutil
from pathlib import Path

from adventure_gis.pack_contract import REQUIRED_PACK_LAYER_KEYS, default_layers_map
from adventure_gis.pack_hash import discovery_stats_for_hash, pack_content_hash
from adventure_gis.pack_validate import validate_pack

FIXTURE = Path("fixtures/karakoram_mini")


def test_discovery_stats_for_hash_accepts_discovery_or_blob() -> None:
    discovery = {"selected_by_generator": {"osm_peak": 2}, "catalog_count": 2}
    blob = {"osm": {}, "discovery": discovery, "content_hash": "deadbeef"}
    assert discovery_stats_for_hash(discovery) == discovery
    assert discovery_stats_for_hash(blob) == discovery
    assert discovery_stats_for_hash(None) == {}
    assert discovery_stats_for_hash({"osm": {}}) == {}


def test_discovery_stats_prefers_nested_when_build_stats_shaped() -> None:
    """Top-level selected_by_generator must not win over .discovery on real blobs."""
    blob = {
        "osm": {"backend": "geofabrik"},
        "selected_by_generator": {},
        "discovery": {"selected_by_generator": {"osm_peak": 3}},
        "dem_tiles": [],
        "content_hash": "abc",
    }
    assert discovery_stats_for_hash(blob)["selected_by_generator"] == {"osm_peak": 3}


def test_pack_content_hash_same_for_blob_and_discovery(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "catalog.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
    )
    discovery = {"selected_by_generator": {"named_waterbody": 1}}
    blob = {"discovery": discovery, "dem_tiles": [], "osm": {}}
    assert pack_content_hash(layers, discovery) == pack_content_hash(layers, blob)


def test_fixture_pack_fingerprint_stable() -> None:
    """Eval-style call: full build_stats absent → empty selected map."""
    root = Path("fixtures/karakoram_mini")
    layers = root / "layers"
    h1 = pack_content_hash(layers, None)
    h2 = pack_content_hash(layers, {"discovery": {}})
    assert h1 == h2
    assert len(h1) == 16
    # Pinned in evaluation/reports/karakoram_mini_baseline.md
    assert h1 == "1aad7575ad0e7000"


def test_default_layers_map_covers_required_keys() -> None:
    m = default_layers_map()
    assert tuple(m) == REQUIRED_PACK_LAYER_KEYS
    assert m["peaks"] == "layers/peaks.geojson"
    assert m["viewpoints"] == "layers/viewpoints.geojson"


def test_validate_pack_requires_notice_for_real_pack(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    # Force non-synthetic + complete layers map + NOTICE missing
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8")
    text = text.replace("synthetic: true", "synthetic: false")
    layers_block = "layers:\n" + "\n".join(
        f"  {k}: layers/{k}.geojson" for k in REQUIRED_PACK_LAYER_KEYS
    )
    pack_yaml.write_text(text + "\n" + layers_block + "\n", encoding="utf-8")
    errs = validate_pack(str(dest))
    assert any("NOTICE" in e for e in errs)


def test_validate_pack_requires_layers_map_for_real_pack(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "NOTICE").write_text("test notice\n", encoding="utf-8")
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8").replace("synthetic: true", "synthetic: false")
    pack_yaml.write_text(text, encoding="utf-8")
    errs = validate_pack(str(dest))
    assert any("layers map" in e for e in errs)


def test_validate_pack_flags_unmapped_layer_file(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "NOTICE").write_text("test notice\n", encoding="utf-8")
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8").replace("synthetic: true", "synthetic: false")
    # Omit peaks from map while file exists on disk
    keys = [k for k in REQUIRED_PACK_LAYER_KEYS if k != "peaks"]
    layers_block = "layers:\n" + "\n".join(f"  {k}: layers/{k}.geojson" for k in keys)
    pack_yaml.write_text(text + "\n" + layers_block + "\n", encoding="utf-8")
    errs = validate_pack(str(dest))
    assert any("peaks.geojson" in e and "not listed" in e for e in errs)
    assert any("missing required keys" in e and "peaks" in e for e in errs)


def test_fixture_still_passes_without_notice_or_layers_map() -> None:
    assert validate_pack("fixtures/karakoram_mini") == []


def test_manifest_retains_layers_map(tmp_path: Path) -> None:
    from adventure_core.config import load_pack_manifest

    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    pack_yaml = dest / "pack.yaml"
    text = pack_yaml.read_text(encoding="utf-8")
    layers_block = "layers:\n" + "\n".join(
        f"  {k}: layers/{k}.geojson" for k in REQUIRED_PACK_LAYER_KEYS
    )
    pack_yaml.write_text(text + "\n" + layers_block + "\n", encoding="utf-8")
    manifest, _ = load_pack_manifest(str(dest))
    assert manifest.layers["catalog"] == "layers/catalog.geojson"
    assert "peaks" in manifest.layers
