"""Markdown export for ranked missions (field notes / eval logs).

Readable companion to GPX export — not a ranking surface.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from adventure_core.schemas import MissionResult, RankedMission

_WS = re.compile(r"\s+")


def _strip_controls(text: str) -> str:
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 0x20)


def _one_line(text: str) -> str:
    """Collapse whitespace so prose cannot inject new Markdown block structure."""
    return _WS.sub(" ", _strip_controls(text)).strip()


def _md_escape_code(text: str) -> str:
    """Safe text for inline code spans (preserve snake_case ids)."""
    return _one_line(text).replace("`", "'")


def _md_escape(text: str) -> str:
    """Neutralize Markdown / HTML pitfalls in untrusted prompt/name/claim text."""
    out: list[str] = []
    for ch in _one_line(text):
        if ch == "\\":
            out.append("\\\\")
        elif ch == "`":
            out.append("\\`")
        elif ch == "*":
            out.append("\\*")
        elif ch == "_":
            out.append("\\_")
        elif ch == "[":
            out.append("\\[")
        elif ch == "]":
            out.append("\\]")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        elif ch == "|":
            out.append("\\|")
        else:
            out.append(ch)
    return "".join(out)


def _require_finite(value: float, *, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    return float(value)


def _validate_lon_lat(lon: float, lat: float, *, context: str) -> None:
    _require_finite(lon, label=f"{context} lon")
    _require_finite(lat, label=f"{context} lat")
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise ValueError(f"{context}: invalid WGS84 lon/lat ({lon}, {lat})")


def _fmt_prefs(result: MissionResult) -> str:
    active = result.request.intent.preferences.active()
    if not active:
        return "_(none active)_"
    parts = [f"{_md_escape_code(k)}={v:.2f}" for k, v in sorted(active.items())]
    return ", ".join(parts)


def _fmt_optional_number(value: float | int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _mission_section(mission: RankedMission, *, rank: int) -> list[str]:
    _validate_lon_lat(mission.lon, mission.lat, context=f"mission rank {rank}")
    score = _require_finite(mission.score, label=f"mission rank {rank} score")
    conf = _require_finite(mission.confidence.value, label=f"mission rank {rank} confidence")
    claim = (mission.claim or "").strip()
    name = (mission.name or "").strip() or f"(unnamed {mission.candidate_id})"

    lines = [
        f"### {rank}. {_md_escape(name)}",
        "",
        f"- **Score:** {score:.3f}",
        f"- **Confidence:** {conf:.0%}",
        f"- **Claim:** {_md_escape(claim) if claim else '—'}",
        f"- **Coordinates:** `{mission.lat:.6f}, {mission.lon:.6f}` (lat, lon)",
        f"- **Candidate id:** `{_md_escape_code(mission.candidate_id)}`",
    ]
    gen = mission.evidence.get("generator") or mission.evidence.get("source")
    if gen:
        lines.append(f"- **Generator / source:** `{_md_escape_code(str(gen))}`")
    if mission.tags:
        tags = ", ".join(f"`{_md_escape_code(t)}`" for t in mission.tags[:12])
        lines.append(f"- **Tags:** {tags}")
    if mission.explanations:
        lines.append("- **Why (ranking):**")
        for reason in mission.explanations[:8]:
            lines.append(f"  - `{_md_escape_code(reason.code)}`: {_md_escape(reason.detail)}")
    lines.append("")
    return lines


def missions_to_markdown(result: MissionResult) -> str:
    """Serialize a ``MissionResult`` to a Markdown mission report.

    Raises ``ValueError`` if a ranked mission has non-finite score/confidence
    or invalid WGS84 coordinates (same honesty bar as GPX export).
    """
    prompt = (result.request.prompt or "").strip() or "(no prompt)"
    intent = result.request.intent
    c = intent.constraints

    if c.origin_lat is not None and c.origin_lon is not None:
        _validate_lon_lat(c.origin_lon, c.origin_lat, context="origin")

    lines: list[str] = [
        f"# TerraQuest mission — `{_md_escape_code(result.pack_id)}`",
        "",
        f"- **Mode:** `{_md_escape_code(result.mode)}`",
        f"- **Pack:** `{_md_escape_code(result.pack_id)}`",
        f"- **Interpreter:** `{_md_escape_code(intent.source)}`",
        f"- **Prompt:** {_md_escape(prompt)}",
        "",
        "## Intent",
        "",
        f"- **Origin:** {_md_escape((c.origin or '').strip()) or '—'}"
        + (
            f" (`{c.origin_lat:.5f}, {c.origin_lon:.5f}`)"
            if c.origin_lat is not None and c.origin_lon is not None
            else ""
        ),
        f"- **Vehicle:** {_md_escape((c.vehicle or '').strip()) or '—'}"
        + (f" (`{_md_escape_code(c.vehicle_class)}`)" if c.vehicle_class else ""),
        f"- **Days:** {_fmt_optional_number(c.days)}",
        f"- **Party size:** {_fmt_optional_number(c.party_size)}",
        f"- **Preferences:** {_fmt_prefs(result)}",
        f"- **Goals:** {', '.join(f'`{_md_escape_code(g)}`' for g in intent.goals) or '—'}",
        "",
        "## Ranked missions",
        "",
    ]

    if not result.missions:
        lines.append("_(no missions ranked)_")
        lines.append("")
    else:
        for i, mission in enumerate(result.missions, start=1):
            lines.extend(_mission_section(mission, rank=i))

    if result.notes:
        lines.append("## Notes")
        lines.append("")
        for note in result.notes:
            text = _md_escape(note)
            if text:
                lines.append(f"- {text}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated by TerraQuest `adventurectl`. Ranking explanations are "
        "deterministic GIS rationale — not a road itinerary._"
    )
    lines.append("")
    return "\n".join(lines)


def write_mission_markdown(path: str | Path, result: MissionResult) -> Path:
    """Write Markdown to ``path``; return the resolved path."""
    out = Path(path).expanduser().resolve()
    if out.exists() and out.is_dir():
        raise OSError(f"Markdown path is a directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(missions_to_markdown(result), encoding="utf-8")
    return out
