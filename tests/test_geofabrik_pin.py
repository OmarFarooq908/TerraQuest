"""Geofabrik dated extract pins + checksum verification (#60)."""

from __future__ import annotations

from pathlib import Path

import pytest
from adventure_packbuilder.geofabrik import (
    assert_geofabrik_url_allowed,
    download_pbf,
    file_md5,
    file_sha256,
    is_latest_geofabrik_url,
    parse_geofabrik_md5_text,
    verify_pbf_checksums,
)


def test_is_latest_geofabrik_url():
    assert is_latest_geofabrik_url("https://download.geofabrik.de/asia/pakistan-latest.osm.pbf")
    assert not is_latest_geofabrik_url("https://download.geofabrik.de/asia/pakistan-260801.osm.pbf")


def test_allow_latest_false_rejects_moving_url():
    with pytest.raises(ValueError, match="allow_latest"):
        assert_geofabrik_url_allowed(
            "https://download.geofabrik.de/asia/pakistan-latest.osm.pbf",
            allow_latest=False,
        )
    assert_geofabrik_url_allowed(
        "https://download.geofabrik.de/asia/pakistan-260801.osm.pbf",
        allow_latest=False,
    )


def test_parse_geofabrik_md5_text():
    assert (
        parse_geofabrik_md5_text("809f431e63dd87be8a69aea0e69c3fbe  pakistan-260801.osm.pbf\n")
        == "809f431e63dd87be8a69aea0e69c3fbe"
    )
    with pytest.raises(ValueError):
        parse_geofabrik_md5_text("not-a-digest")


def test_verify_pbf_checksums_md5_and_sha256(tmp_path: Path):
    pbf = tmp_path / "tiny.osm.pbf"
    # Must be > 1_000_000 bytes for download_pbf cache reuse path; verify itself has no size gate.
    payload = b"terraquest-pbf-fixture\n" * 80_000
    pbf.write_bytes(payload)
    md5 = file_md5(pbf)
    sha = file_sha256(pbf)
    assert verify_pbf_checksums(pbf, expected_md5=md5, expected_sha256=sha) == {
        "md5": md5,
        "sha256": sha,
    }
    with pytest.raises(ValueError, match="md5 mismatch"):
        verify_pbf_checksums(pbf, expected_md5="0" * 32)


def test_download_pbf_reuses_cache_when_checksum_matches(tmp_path: Path, monkeypatch):
    dest = tmp_path / "region.osm.pbf"
    payload = b"cached-geofabrik-bytes\n" * 80_000
    dest.write_bytes(payload)
    md5 = file_md5(dest)

    def _boom(*_a, **_k):  # pragma: no cover - must not be called
        raise AssertionError("httpx should not be used when cache verifies")

    monkeypatch.setattr("adventure_packbuilder.geofabrik.httpx.Client", _boom)
    out = download_pbf(
        "https://download.geofabrik.de/asia/pakistan-260801.osm.pbf",
        dest,
        expected_md5=md5,
        allow_latest=False,
    )
    assert out == dest


def test_download_pbf_refuses_latest_before_network(tmp_path: Path):
    with pytest.raises(ValueError, match="allow_latest"):
        download_pbf(
            "https://download.geofabrik.de/asia/pakistan-latest.osm.pbf",
            tmp_path / "x.osm.pbf",
            allow_latest=False,
        )


def test_download_pbf_replaces_stale_cache_on_md5_mismatch(tmp_path: Path, monkeypatch):
    dest = tmp_path / "region.osm.pbf"
    stale = b"stale-geofabrik-cache\n" * 80_000
    dest.write_bytes(stale)
    fresh = b"fresh-geofabrik-bytes\n" * 80_000
    want_md5 = __import__("hashlib").md5(fresh).hexdigest()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self, chunk_size: int = 0):
            yield fresh

    class _StreamCM:
        def __enter__(self):
            return _Resp()

        def __exit__(self, *args):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return _StreamCM()

    monkeypatch.setattr("adventure_packbuilder.geofabrik.httpx.Client", _Client)
    out = download_pbf(
        "https://download.geofabrik.de/asia/pakistan-260801.osm.pbf",
        dest,
        expected_md5=want_md5,
        allow_latest=False,
    )
    assert out.read_bytes() == fresh
    assert file_md5(out) == want_md5


def test_skardu_v1_config_is_dated_pin():
    from adventure_core.config import configs_dir, load_yaml

    raw = load_yaml(configs_dir() / "packs" / "skardu_v1.yaml")
    osm = raw["osm"]
    assert osm["allow_latest"] is False
    assert "latest" not in osm["geofabrik_url"]
    assert osm["geofabrik_md5"] == "809f431e63dd87be8a69aea0e69c3fbe"
    assert osm["cache_pbf"] == "pakistan-260801.osm.pbf"
