"""Coverage gate checks (issue #16)."""

from __future__ import annotations

import json
from pathlib import Path

from adventure_core.config import repo_root
from adventure_core.coverage_gates import check_coverage, load_gates, match_module

GATES = repo_root() / "configs" / "coverage_gates.yaml"


def _report_above_floors() -> dict:
    """Synthetic coverage.json that sits a few points above every configured floor."""
    global_floor, modules = load_gates(GATES)
    files = {
        f"packages/src/{suffix}": {"summary": {"percent_covered": floor + 5.0}}
        for suffix, floor in modules.items()
    }
    return {
        "totals": {"percent_covered": max(global_floor + 5.0, 85.0)},
        "files": files,
    }


def test_gates_pass_when_all_modules_above_floor(tmp_path: Path):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_report_above_floors()), encoding="utf-8")
    assert check_coverage(path, GATES) == []


def test_gates_fail_when_module_below_floor(tmp_path: Path):
    _, modules = load_gates(GATES)
    first = next(iter(modules))
    report = {
        "totals": {"percent_covered": 85.0},
        "files": {
            f"packages/core/src/{first}": {"summary": {"percent_covered": modules[first] - 10.0}},
        },
    }
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    errs = check_coverage(path, GATES)
    assert any(first in e and "< floor" in e for e in errs)
    assert any("missing coverage data" in e for e in errs)


def test_gates_fail_on_global_floor(tmp_path: Path):
    global_floor, _ = load_gates(GATES)
    report = _report_above_floors()
    report["totals"]["percent_covered"] = global_floor - 1.0
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    errs = check_coverage(path, GATES)
    assert any("global coverage" in e for e in errs)


def test_match_module_suffix_and_absolute_paths():
    assert match_module(
        "/home/runner/work/TerraQuest/packages/core/src/adventure_core/intent.py",
        "adventure_core/intent.py",
    )
    assert match_module("adventure_core/intent.py", "adventure_core/intent.py")
    assert not match_module("foo/intent.py", "adventure_core/intent.py")
    assert not match_module(
        "packages/core/src/adventure_core/intent_validate.py",
        "adventure_core/intent.py",
    )


def test_yaml_global_floor_matches_pyproject_and_ci():
    """Keep pyproject fail_under, CI flag, and YAML global_fail_under in lockstep."""
    global_floor, _ = load_gates(GATES)
    floor_i = int(global_floor)
    text = (repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    assert f"fail_under = {floor_i}" in text
    ci = (repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"--cov-fail-under={floor_i}" in ci
