"""Offline pack verify CLI + report (issue #70)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from adventure_cli.main import app
from adventure_gis import verify_pack
from adventure_gis.pack_hash import pack_content_hash
from typer.testing import CliRunner

FIXTURE = "fixtures/karakoram_mini"
runner = CliRunner()


def test_verify_pack_fixture_ok() -> None:
    report = verify_pack(FIXTURE)
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["pack_id"] == "karakoram_mini"
    assert report["synthetic"] is True
    assert report["catalog_count"] >= 1
    assert report["fingerprint"]
    assert len(report["fingerprint"]) == 16
    assert report["content_hash"] is None
    assert report["hash_match"] is None


def test_verify_pack_reports_errors(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "layers" / "catalog.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}',
        encoding="utf-8",
    )
    report = verify_pack(str(dest))
    assert report["ok"] is False
    assert report["errors"]


def test_hash_match_none_when_build_stats_missing(tmp_path: Path) -> None:
    """Declared content_hash without build_stats must not report a false match."""
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "build_stats.json").unlink(missing_ok=True)
    fp = pack_content_hash(dest / "layers", None)
    text = (dest / "pack.yaml").read_text(encoding="utf-8")
    (dest / "pack.yaml").write_text(text + f"\ncontent_hash: {fp}\n", encoding="utf-8")
    report = verify_pack(str(dest))
    assert report["ok"] is False
    assert any("build_stats.json is missing" in e for e in report["errors"])
    assert report["fingerprint"] == fp
    assert report["content_hash"] == fp
    assert report["hash_match"] is None


def test_hash_match_false_on_mismatch(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "build_stats.json").write_text(
        json.dumps({"osm": {}, "discovery": {"selected_by_generator": {"peak": 1}}}),
        encoding="utf-8",
    )
    text = (dest / "pack.yaml").read_text(encoding="utf-8")
    (dest / "pack.yaml").write_text(
        text + "\ncontent_hash: deadbeefdeadbeef\n",
        encoding="utf-8",
    )
    report = verify_pack(str(dest))
    assert report["ok"] is False
    assert report["hash_match"] is False
    assert any("content_hash mismatch" in e for e in report["errors"])


def test_corrupt_build_stats_without_content_hash_warns(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    (dest / "build_stats.json").write_text("{not-json", encoding="utf-8")
    report = verify_pack(str(dest))
    assert report["ok"] is True
    assert report["fingerprint"]
    assert any("build_stats.json is not valid JSON" in w for w in report["warnings"])


def test_corrupt_build_stats_with_content_hash_errors(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    text = (dest / "pack.yaml").read_text(encoding="utf-8")
    (dest / "pack.yaml").write_text(text + "\ncontent_hash: deadbeefdeadbeef\n", encoding="utf-8")
    (dest / "build_stats.json").write_text("{not-json", encoding="utf-8")
    report = verify_pack(str(dest))
    assert report["ok"] is False
    assert any("build_stats.json is not valid JSON" in e for e in report["errors"])
    assert report["hash_match"] is None


def test_stale_query_db_warns_but_ok(tmp_path: Path) -> None:
    from adventure_gis.pack_query import materialize_pack_db

    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    materialize_pack_db(dest)
    cat = json.loads((dest / "layers" / "catalog.geojson").read_text(encoding="utf-8"))
    cat["features"][0]["properties"]["name"] = "MUTATED-FOR-STALE-DB"
    (dest / "layers" / "catalog.geojson").write_text(json.dumps(cat), encoding="utf-8")
    report = verify_pack(str(dest))
    assert report["ok"] is True
    assert report["query_db"] is not None
    assert report["query_db"]["stale"] is True
    assert any("stale" in w for w in report["warnings"])


def test_cli_pack_verify_ok() -> None:
    result = runner.invoke(app, ["pack", "verify", "--pack", FIXTURE])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "fingerprint=" in result.output
    assert "SYNTHETIC" in result.output


def test_cli_pack_verify_json() -> None:
    result = runner.invoke(app, ["pack", "verify", "--pack", FIXTURE, "--json"])
    assert result.exit_code == 0, result.output
    # Machine-readable: stdout must be pure JSON (no honesty banner).
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["fingerprint"]
    assert payload["pack_id"] == "karakoram_mini"
    assert "warnings" in payload
    assert "SYNTHETIC" not in result.stdout


def test_cli_pack_verify_fail_exit(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    text = (dest / "pack.yaml").read_text(encoding="utf-8")
    (dest / "pack.yaml").write_text(
        text.replace("synthetic: true", "synthetic: false"),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["pack", "verify", "--pack", str(dest)])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "NOTICE" in result.output


def test_cli_pack_verify_json_fail_still_emits_report(tmp_path: Path) -> None:
    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    text = (dest / "pack.yaml").read_text(encoding="utf-8")
    (dest / "pack.yaml").write_text(
        text.replace("synthetic: true", "synthetic: false"),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["pack", "verify", "--pack", str(dest), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"]


def test_pack_help_lists_verify() -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0
    assert "verify" in result.stdout
