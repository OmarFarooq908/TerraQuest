"""Offline pack verify CLI + report (issue #70)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from adventure_cli.main import app
from adventure_gis import verify_pack
from typer.testing import CliRunner

FIXTURE = "fixtures/karakoram_mini"
runner = CliRunner()


def test_verify_pack_fixture_ok() -> None:
    report = verify_pack(FIXTURE)
    assert report["ok"] is True
    assert report["errors"] == []
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


def test_cli_pack_verify_ok() -> None:
    result = runner.invoke(app, ["pack", "verify", "--pack", FIXTURE])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "fingerprint=" in result.output


def test_cli_pack_verify_json() -> None:
    result = runner.invoke(app, ["pack", "verify", "--pack", FIXTURE, "--json"])
    assert result.exit_code == 0, result.output
    start = result.stdout.find("{")
    assert start >= 0
    payload = json.loads(result.stdout[start:])
    assert payload["ok"] is True
    assert payload["fingerprint"]
    assert payload["pack_id"] == "karakoram_mini"


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


def test_pack_help_lists_verify() -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0
    assert "verify" in result.stdout
