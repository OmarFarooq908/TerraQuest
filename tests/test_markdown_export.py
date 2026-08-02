"""Markdown mission export (issue #68)."""

from __future__ import annotations

from pathlib import Path

import pytest
from adventure_core.intent import HardConstraints, MissionIntent
from adventure_core.markdown_export import missions_to_markdown, write_mission_markdown
from adventure_core.schemas import (
    Confidence,
    MissionRequest,
    MissionResult,
    RankedMission,
    ReasonCode,
)


def _mission(
    *,
    cid: str,
    name: str,
    lon: float,
    lat: float,
    score: float,
    claim: str = "test claim",
) -> RankedMission:
    return RankedMission(
        candidate_id=cid,
        name=name,
        claim=claim,
        lon=lon,
        lat=lat,
        score=score,
        confidence=Confidence(
            value=0.7,
            reasons=[ReasonCode(code="test", detail="unit")],
        ),
        feature_breakdown={},
        explanations=[ReasonCode(code="pref_water", detail="water +0.4")],
        tags=["water", "remote"],
        evidence={"generator": "named_waterbody"},
    )


def _result(missions: list[RankedMission], *, with_origin: bool = False) -> MissionResult:
    hc = HardConstraints()
    if with_origin:
        hc = HardConstraints(
            origin="Skardu",
            origin_lon=75.63,
            origin_lat=35.30,
            vehicle="Suzuki Swift",
            vehicle_class="hatchback",
            days=3,
            party_size=2,
        )
    intent = MissionIntent(constraints=hc, goals=["discovery"])
    intent.preferences.water = 0.8
    intent.preferences.human_activity = -0.9
    return MissionResult(
        request=MissionRequest(
            prompt='Three days near Skardu — <script>alert("x")</script> **bold**',
            pack_id="fixtures/karakoram_mini",
            mode="fearless_far",
            intent=intent,
            max_results=5,
        ),
        mode="fearless_far",
        pack_id="fixtures/karakoram_mini",
        missions=missions,
        notes=["pack_kind=synthetic"],
    )


def test_markdown_includes_ranks_and_escapes() -> None:
    result = _result(
        [
            _mission(cid="a", name="Lake *Ridge*", lon=75.18, lat=35.72, score=0.9),
            _mission(cid="b", name="Valley_X", lon=74.72, lat=35.82, score=0.8),
        ],
        with_origin=True,
    )
    md = missions_to_markdown(result)
    assert md.startswith("# TerraQuest mission")
    assert "### 1. Lake \\*Ridge\\*" in md
    assert "### 2. Valley\\_X" in md
    assert "&lt;script&gt;" in md
    assert "**bold**" not in md or "\\*\\*bold\\*\\*" in md
    assert "pref_water" in md
    assert "named_waterbody" in md
    assert "human_activity=-0.90" in md
    assert "pack\\_kind=synthetic" in md or "pack_kind=synthetic" in md
    assert "35.720000, 75.180000" in md


def test_markdown_empty_missions() -> None:
    md = missions_to_markdown(_result([]))
    assert "_(no missions ranked)_" in md


def test_write_mission_markdown(tmp_path: Path) -> None:
    out = tmp_path / "notes" / "mission.md"
    path = write_mission_markdown(
        out, _result([_mission(cid="a", name="A", lon=1, lat=2, score=0.5)])
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "### 1. A" in text


def test_write_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="directory"):
        write_mission_markdown(tmp_path, _result([]))


def test_cli_export_md_smoke(tmp_path: Path) -> None:
    from adventure_cli.main import app
    from typer.testing import CliRunner

    out = tmp_path / "mission.md"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "mission",
            "run",
            "--pack",
            "fixtures/karakoram_mini",
            "--interpreter",
            "rules",
            "-p",
            "Three days, rivers and forests, hate crowds.",
            "--export-md",
            str(out),
            "--max-results",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "# TerraQuest mission" in text
    assert "### 1." in text
    assert "Wrote Markdown" in result.output
