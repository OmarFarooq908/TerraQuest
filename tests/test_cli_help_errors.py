"""Regression coverage for clarified CLI help and pack/osmium errors (#7)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from adventure_cli.main import app
from adventure_core.config import load_pack_manifest
from adventure_packbuilder.geofabrik import require_osmium
from typer.testing import CliRunner

runner = CliRunner()


def test_mission_run_help_distinguishes_fixture_vs_built() -> None:
    result = runner.invoke(app, ["mission", "run", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "fixtures/" in out
    assert "offline" in out.lower() or "CI" in out
    assert "Built pack" in out or "built pack" in out
    assert "interpreter" in out.lower()


def test_pack_build_help_mentions_osmium_and_not_fixtures() -> None:
    result = runner.invoke(app, ["pack", "build", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "osmium" in out.lower()
    assert "fixtures/" in out
    assert "not a fixtures" in out.lower() or "do not pass" in out.lower()


def test_top_level_pack_help_mentions_osmium() -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0
    assert "osmium" in result.stdout.lower()


def test_require_osmium_error_points_to_install_and_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("adventure_packbuilder.geofabrik.shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError) as exc:
        require_osmium()
    msg = str(exc.value)
    assert "osmium-tool" in msg
    assert "brew install osmium-tool" in msg
    assert "fixtures/karakoram_mini" in msg
    assert "mission run" in msg


def test_require_osmium_returns_path_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "adventure_packbuilder.geofabrik.shutil.which",
        lambda _name: "/usr/bin/osmium",
    )
    assert require_osmium() == "/usr/bin/osmium"


def test_unbuilt_pack_error_suggests_build_and_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "configs" / "modes").mkdir(parents=True)
    packs = tmp_path / "configs" / "packs"
    packs.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='qa'\n", encoding="utf-8")
    pack_id = "qa_unbuilt_v1"
    (packs / f"{pack_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "pack_id": pack_id,
                "name": "QA unbuilt pack",
                "bbox": [75.0, 35.0, 76.0, 36.0],
                "crs": "EPSG:4326",
                "feature_schema_version": "0.3.0",
                "synthetic": False,
                "output_dir": f"data/packs/{pack_id}",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("adventure_core.config.repo_root", lambda: tmp_path)

    with pytest.raises(FileNotFoundError) as exc:
        load_pack_manifest(pack_id)
    msg = str(exc.value)
    assert "not built" in msg
    assert f"pack build --config {pack_id}" in msg
    assert "osmium-tool" in msg
    assert "fixtures/karakoram_mini" in msg


def test_fixture_pack_still_resolves() -> None:
    manifest, pack_dir = load_pack_manifest("fixtures/karakoram_mini")
    assert manifest.synthetic is True
    assert pack_dir.name == "karakoram_mini"
    assert (pack_dir / "pack.yaml").is_file()
