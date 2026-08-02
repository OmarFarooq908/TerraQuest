"""GPX 1.1 export for ranked missions (field eval / phone GPS).

Track order is rank order (optional origin first). This is **not** a road
router — see ``docs/known-limits.md``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from adventure_core.schemas import MissionResult, RankedMission

GPX_NS = "http://www.topografix.com/GPX/1/1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
GPX_SCHEMA_LOC = "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"
GPX_CREATOR = "TerraQuest adventurectl"


def _xml_safe(text: str) -> str:
    """Strip characters illegal in XML 1.0 text nodes (keeps tab/LF/CR)."""
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 0x20)


def _el(tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    elem = ET.Element(tag, {k: v for k, v in attrs.items() if v is not None})
    if text is not None:
        elem.text = _xml_safe(text)
    return elem


def _wpt_desc(mission: RankedMission, *, rank: int) -> str:
    parts = [
        f"rank={rank}",
        f"score={mission.score:.3f}",
        f"confidence={mission.confidence.value:.0%}",
        f"candidate_id={mission.candidate_id}",
    ]
    if mission.claim:
        parts.append(f"claim={mission.claim}")
    if mission.explanations:
        why = "; ".join(f"{r.code}: {r.detail}" for r in mission.explanations[:5])
        parts.append(f"why={why}")
    return " | ".join(parts)


def _validate_lon_lat(lon: float, lat: float, *, context: str) -> None:
    # NaN/Inf fail these comparisons in IEEE/Python.
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise ValueError(f"{context}: invalid WGS84 lon/lat ({lon}, {lat})")


def missions_to_gpx(
    result: MissionResult,
    *,
    include_track: bool = True,
    creator: str = GPX_CREATOR,
) -> str:
    """Serialize a ``MissionResult`` to a GPX 1.1 document string."""
    ET.register_namespace("", GPX_NS)
    ET.register_namespace("xsi", XSI_NS)

    root = ET.Element(
        f"{{{GPX_NS}}}gpx",
        {
            "version": "1.1",
            "creator": creator,
            f"{{{XSI_NS}}}schemaLocation": GPX_SCHEMA_LOC,
        },
    )

    meta = _el(f"{{{GPX_NS}}}metadata")
    prompt = (result.request.prompt or "").strip() or "(no prompt)"
    meta.append(_el(f"{{{GPX_NS}}}name", f"TerraQuest mission — {result.pack_id}"))
    meta.append(
        _el(
            f"{{{GPX_NS}}}desc",
            f"pack={result.pack_id}; mode={result.mode}; prompt={prompt[:240]}",
        )
    )
    root.append(meta)

    origin_lon = result.request.intent.constraints.origin_lon
    origin_lat = result.request.intent.constraints.origin_lat
    origin_name = result.request.intent.constraints.origin
    track_points: list[tuple[float, float, str]] = []

    if origin_lon is not None and origin_lat is not None:
        _validate_lon_lat(origin_lon, origin_lat, context="origin")
        label = origin_name or "origin"
        wpt = _el(
            f"{{{GPX_NS}}}wpt",
            lat=f"{origin_lat:.7f}",
            lon=f"{origin_lon:.7f}",
        )
        wpt.append(_el(f"{{{GPX_NS}}}name", f"Origin: {label}"))
        wpt.append(_el(f"{{{GPX_NS}}}type", "origin"))
        wpt.append(
            _el(
                f"{{{GPX_NS}}}desc",
                "Mission origin (not a ranked discovery). Track order is haversine, not routed.",
            )
        )
        root.append(wpt)
        track_points.append((origin_lat, origin_lon, label))

    for i, mission in enumerate(result.missions, start=1):
        _validate_lon_lat(mission.lon, mission.lat, context=mission.candidate_id)
        wpt = _el(
            f"{{{GPX_NS}}}wpt",
            lat=f"{mission.lat:.7f}",
            lon=f"{mission.lon:.7f}",
        )
        wpt.append(_el(f"{{{GPX_NS}}}name", f"{i}. {mission.name}"))
        wpt.append(_el(f"{{{GPX_NS}}}cmt", mission.candidate_id))
        wpt.append(_el(f"{{{GPX_NS}}}desc", _wpt_desc(mission, rank=i)))
        wpt.append(_el(f"{{{GPX_NS}}}type", "ranked_mission"))
        root.append(wpt)
        track_points.append((mission.lat, mission.lon, mission.name))

    if include_track and len(track_points) >= 2:
        trk = _el(f"{{{GPX_NS}}}trk")
        trk.append(_el(f"{{{GPX_NS}}}name", "Rank order (not routed)"))
        trk.append(
            _el(
                f"{{{GPX_NS}}}desc",
                "Polyline connects origin (if any) then ranked missions in score order. "
                "Haversine / display only — not a road graph.",
            )
        )
        seg = _el(f"{{{GPX_NS}}}trkseg")
        for lat, lon, _name in track_points:
            seg.append(
                _el(
                    f"{{{GPX_NS}}}trkpt",
                    lat=f"{lat:.7f}",
                    lon=f"{lon:.7f}",
                )
            )
        trk.append(seg)
        root.append(trk)

    # Prefer ElementTree indent over minidom round-trip (minidom re-parses and
    # rejects illegal control chars even after we could have escaped entities).
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def write_mission_gpx(
    path: str | Path,
    result: MissionResult,
    *,
    include_track: bool = True,
) -> Path:
    """Write GPX to ``path``; return the resolved path."""
    out = Path(path).expanduser().resolve()
    if out.exists() and out.is_dir():
        raise OSError(f"GPX path is a directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        missions_to_gpx(result, include_track=include_track),
        encoding="utf-8",
    )
    return out


def gpx_waypoint_count(gpx_xml: str) -> int:
    """Count ``wpt`` elements (helper for tests)."""
    root = ET.fromstring(gpx_xml)
    return len(root.findall(f"{{{GPX_NS}}}wpt"))
