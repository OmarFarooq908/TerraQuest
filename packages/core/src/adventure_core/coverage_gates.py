"""Per-module coverage floors for P0 correctness paths (issue #16)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def load_gates(path: Path) -> tuple[float, dict[str, float]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    global_floor = float(data["global_fail_under"])
    modules = {str(k): float(v) for k, v in (data.get("modules") or {}).items()}
    return global_floor, modules


def match_module(file_path: str, module_suffix: str) -> bool:
    """True if coverage file path is the gated module (suffix match only)."""
    norm = file_path.replace("\\", "/").rstrip("/")
    suffix = module_suffix.replace("\\", "/").lstrip("/")
    return norm.endswith(suffix)


def check_coverage(coverage_json: Path, gates_path: Path) -> list[str]:
    """Return actionable error strings (empty = ok)."""
    global_floor, modules = load_gates(gates_path)
    blob = json.loads(coverage_json.read_text(encoding="utf-8"))
    total = float(blob["totals"]["percent_covered"])
    errors: list[str] = []

    if total < global_floor:
        errors.append(f"global coverage {total:.1f}% < floor {global_floor:.0f}%")

    files = blob.get("files") or {}
    for suffix, floor in modules.items():
        matches = [
            float(meta["summary"]["percent_covered"])
            for path, meta in files.items()
            if match_module(path, suffix)
        ]
        if not matches:
            errors.append(f"missing coverage data for gated module {suffix}")
            continue
        pct = min(matches)
        if pct < floor:
            errors.append(f"{suffix}: {pct:.1f}% < floor {floor:.0f}%")

    return errors
