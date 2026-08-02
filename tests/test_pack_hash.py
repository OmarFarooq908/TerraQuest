"""Pack content hash + contract validation (RFC-0003 / issue #18 / #62)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from adventure_gis.pack_contract import REQUIRED_PACK_LAYER_KEYS, default_layers_map
from adventure_gis.pack_hash import (
    PACK_CONTENT_HASH_VERSION,
    discovery_payload_for_hash,
    discovery_stats_for_hash,
    layer_file_digests,
    pack_content_hash,
)
from adventure_gis.pack_validate import validate_pack

FIXTURE = Path("fixtures/karakoram_mini")
# Pinned in evaluation/reports/karakoram_mini_baseline.md (pack-content v2).
FIXTURE_PACK_CONTENT_HASH_V2 = "f7f6a397fd5fef00"


def test_discovery_stats_for_hash_accepts_discovery_or_blob() -> None:
    discovery = {"selected_by_generator": {"osm_peak": 2}, "catalog_count": 2}
    blob = {"osm": {}, "discovery": discovery, "content_hash": "deadbeef"}
    assert discovery_stats_for_hash(discovery) == discovery
    assert discovery_stats_for_hash(blob) == discovery
    assert discovery_stats_for_hash(None) == {}
    assert discovery_stats_for_hash({"osm": {}}) == {}


def test_discovery_stats_keeps_knobs_without_selected_by_generator() -> None:
    """Partial discovery dicts must not be silently wiped to {}."""
    partial = {"min_spacing_km": 0.6, "quotas": {"osm_peak": 3}}
    assert discovery_stats_for_hash(partial) == partial


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
    discovery = {
        "selected_by_generator": {"named_waterbody": 1},
        "quotas": {"named_waterbody": 2},
        "min_spacing_km": 1.5,
        "grid_res_deg": 0.02,
        "catalog_schema_version": "0.3.0",
        "generators_run": ["named_waterbody"],
    }
    blob = {"discovery": discovery, "dem_tiles": [], "osm": {}}
    assert pack_content_hash(layers, discovery) == pack_content_hash(layers, blob)


def test_discovery_payload_sorts_generators_run() -> None:
    payload = discovery_payload_for_hash(
        {
            "generators_run": ["b", "a"],
            "catalog_count": 9,  # not hashed
            "selected_by_generator": {"a": 1},
        }
    )
    assert payload["generators_run"] == ["a", "b"]
    assert "catalog_count" not in payload


def test_fixture_pack_fingerprint_stable() -> None:
    """Eval-style call: full build_stats absent → empty discovery payload."""
    root = Path("fixtures/karakoram_mini")
    layers = root / "layers"
    h1 = pack_content_hash(layers, None)
    h2 = pack_content_hash(layers, {"discovery": {}})
    assert h1 == h2
    assert len(h1) == 16
    assert PACK_CONTENT_HASH_VERSION == 2
    assert h1 == FIXTURE_PACK_CONTENT_HASH_V2


def test_pack_content_hash_changes_with_discovery_knobs(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "catalog.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
    )
    base = {
        "selected_by_generator": {"osm_peak": 1},
        "quotas": {"osm_peak": 3},
        "min_spacing_km": 2.0,
        "spacing_by_generator": {"osm_peak": 2.0, "road_spur": 0.8},
        "grid_res_deg": 0.02,
        "catalog_schema_version": "0.3.0",
        "generators_run": ["osm_peak"],
    }
    h0 = pack_content_hash(layers, base)
    for key, val in (
        ("quotas", {"osm_peak": 4}),
        ("min_spacing_km", 3.0),
        ("spacing_by_generator", {"osm_peak": 2.5, "road_spur": 0.8}),
        ("grid_res_deg", 0.01),
        ("catalog_schema_version", "0.4.0"),
        ("generators_run", ["osm_peak", "road_spur"]),
        ("selected_by_generator", {"osm_peak": 2}),
    ):
        mutated = dict(base)
        mutated[key] = val
        assert pack_content_hash(layers, mutated) != h0, key


def test_pack_content_hash_rejects_nan_discovery_values(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "catalog.geojson").write_text("{}", encoding="utf-8")
    try:
        pack_content_hash(layers, {"min_spacing_km": float("nan")})
    except ValueError:
        return
    raise AssertionError("expected ValueError for NaN discovery values")


def test_spacing_knob_alone_affects_hash(tmp_path: Path) -> None:
    """Regression: knobs must hash even without selected_by_generator."""
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "catalog.geojson").write_text("{}", encoding="utf-8")
    assert pack_content_hash(layers, {"min_spacing_km": 0.6}) != pack_content_hash(
        layers, {"min_spacing_km": 0.9}
    )


def test_pack_content_hash_changes_with_layer_bytes(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    path = layers / "catalog.geojson"
    path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    h0 = pack_content_hash(layers, None)
    path.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature"}]}',
        encoding="utf-8",
    )
    assert pack_content_hash(layers, None) != h0


def test_pack_content_hash_domain_version_changes_digest(tmp_path: Path) -> None:
    """Domain separator must matter: empty payload still differs from raw layer hash."""
    layers = tmp_path / "layers"
    layers.mkdir()
    raw = b'{"type":"FeatureCollection","features":[]}'
    (layers / "catalog.geojson").write_bytes(raw)
    # Naive concat without domain/version must not collide with v2.
    naive = hashlib.sha256()
    naive.update(b"catalog.geojson\0")
    naive.update(raw)
    naive.update(b"\0")
    naive.update(b"{}")
    assert pack_content_hash(layers, None) != naive.hexdigest()[:16]


def test_layer_file_digests_match_sha256(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    a = layers / "a.geojson"
    b = layers / "b.geojson"
    a.write_text("aaa", encoding="utf-8")
    b.write_text("bbb", encoding="utf-8")
    digests = layer_file_digests(layers)
    assert digests == {
        "a.geojson": hashlib.sha256(b"aaa").hexdigest(),
        "b.geojson": hashlib.sha256(b"bbb").hexdigest(),
    }


def test_fixture_layer_digests_cover_geojson() -> None:
    digests = layer_file_digests(FIXTURE / "layers")
    assert "catalog.geojson" in digests
    assert len(digests["catalog.geojson"]) == 64
    assert len(digests) == len(list((FIXTURE / "layers").glob("*.geojson")))


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
