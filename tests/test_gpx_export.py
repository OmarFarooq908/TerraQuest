"""GPX export for ranked missions (issue #58)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from adventure_core.gpx import (
    GPX_NS,
    gpx_waypoint_count,
    missions_to_gpx,
    write_mission_gpx,
)
from adventure_core.intent import HardConstraints, MissionIntent
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
    )


def _result(missions: list[RankedMission], *, with_origin: bool = False) -> MissionResult:
    hc = HardConstraints()
    if with_origin:
        hc = HardConstraints(origin="Skardu", origin_lon=75.63, origin_lat=35.30)
    return MissionResult(
        request=MissionRequest(
            prompt='Three days near Skardu — <script>alert("x")</script>',
            pack_id="fixtures/karakoram_mini",
            mode="fearless_far",
            intent=MissionIntent(constraints=hc),
            max_results=5,
        ),
        mode="fearless_far",
        pack_id="fixtures/karakoram_mini",
        missions=missions,
    )


def test_gpx_has_waypoints_and_escapes_xml():
    result = _result(
        [
            _mission(cid="a", name="Lake & Ridge", lon=75.18, lat=35.72, score=0.9),
            _mission(cid="b", name="Valley", lon=74.72, lat=35.82, score=0.8),
        ]
    )
    xml = missions_to_gpx(result)
    assert xml.startswith("<?xml")
    assert 'version="1.1"' in xml
    assert gpx_waypoint_count(xml) == 2
    assert "&amp;" in xml or "Lake &amp; Ridge" in xml
    assert "<script>" not in xml
    root = ET.fromstring(xml)
    names = [e.findtext(f"{{{GPX_NS}}}name") for e in root.findall(f"{{{GPX_NS}}}wpt")]
    assert names[0] == "1. Lake & Ridge"
    assert root.find(f"{{{GPX_NS}}}trk") is not None


def test_gpx_includes_origin_waypoint_and_track_order():
    result = _result(
        [_mission(cid="a", name="Lake", lon=75.18, lat=35.72, score=0.9)],
        with_origin=True,
    )
    xml = missions_to_gpx(result)
    assert gpx_waypoint_count(xml) == 2
    root = ET.fromstring(xml)
    types = [e.findtext(f"{{{GPX_NS}}}type") for e in root.findall(f"{{{GPX_NS}}}wpt")]
    assert types[0] == "origin"
    assert types[1] == "ranked_mission"
    trkpts = root.findall(f".//{{{GPX_NS}}}trkpt")
    assert len(trkpts) == 2
    assert trkpts[0].attrib["lat"].startswith("35.30")
    assert trkpts[1].attrib["lat"].startswith("35.72")


def test_gpx_no_track_when_disabled_or_single_point():
    one = _result([_mission(cid="a", name="Only", lon=75.0, lat=35.0, score=0.5)])
    xml = missions_to_gpx(one, include_track=True)
    assert ET.fromstring(xml).find(f"{{{GPX_NS}}}trk") is None

    two = _result(
        [
            _mission(cid="a", name="A", lon=75.0, lat=35.0, score=0.5),
            _mission(cid="b", name="B", lon=75.1, lat=35.1, score=0.4),
        ]
    )
    xml2 = missions_to_gpx(two, include_track=False)
    assert ET.fromstring(xml2).find(f"{{{GPX_NS}}}trk") is None


def test_gpx_rejects_invalid_coordinates():
    bad = _result([_mission(cid="x", name="Bad", lon=999.0, lat=35.0, score=0.1)])
    with pytest.raises(ValueError, match="invalid WGS84"):
        missions_to_gpx(bad)


def test_write_mission_gpx(tmp_path: Path):
    result = _result(
        [
            _mission(cid="a", name="Lake", lon=75.18, lat=35.72, score=0.9),
            _mission(cid="b", name="Valley", lon=74.72, lat=35.82, score=0.8),
        ]
    )
    path = write_mission_gpx(tmp_path / "out" / "mission.gpx", result)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert gpx_waypoint_count(text) == 2


def test_cli_export_gpx_smoke(tmp_path: Path):
    from adventure_cli.main import app
    from typer.testing import CliRunner

    out = tmp_path / "mission.gpx"
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
            "--export-gpx",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert gpx_waypoint_count(out.read_text(encoding="utf-8")) >= 1
