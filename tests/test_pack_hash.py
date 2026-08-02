"""Pack content hash normalization (RFC-0003 / issue #18)."""

from __future__ import annotations

from pathlib import Path

from adventure_gis.pack_hash import discovery_stats_for_hash, pack_content_hash


def test_discovery_stats_for_hash_accepts_discovery_or_blob() -> None:
    discovery = {"selected_by_generator": {"osm_peak": 2}, "catalog_count": 2}
    blob = {"osm": {}, "discovery": discovery, "content_hash": "deadbeef"}
    assert discovery_stats_for_hash(discovery) == discovery
    assert discovery_stats_for_hash(blob) == discovery
    assert discovery_stats_for_hash(None) == {}
    assert discovery_stats_for_hash({"osm": {}}) == {}


def test_pack_content_hash_same_for_blob_and_discovery(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "catalog.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
    )
    discovery = {"selected_by_generator": {"named_waterbody": 1}}
    blob = {"discovery": discovery, "dem_tiles": []}
    assert pack_content_hash(layers, discovery) == pack_content_hash(layers, blob)


def test_fixture_pack_fingerprint_stable() -> None:
    """Eval-style call: full build_stats absent → empty selected map."""
    root = Path("fixtures/karakoram_mini")
    layers = root / "layers"
    h1 = pack_content_hash(layers, None)
    h2 = pack_content_hash(layers, {"discovery": {}})
    assert h1 == h2
    assert len(h1) == 16
