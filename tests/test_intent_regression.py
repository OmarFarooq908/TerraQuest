"""Intent regression suite from eval/golden_prompts.yaml (issue #12)."""

from __future__ import annotations

import os
from typing import Any

import pytest
import yaml
from adventure_core.config import repo_root
from adventure_core.intent import PreferenceVector
from adventure_inference.router import interpret_mission

GOLDEN_PATH = repo_root() / "eval" / "golden_prompts.yaml"
NEAR_NEUTRAL_ABS = 0.25


def _load_cases() -> list[dict[str, Any]]:
    data = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(data["prompts"])


CASES = _load_cases()
RULES_CASES = [c for c in CASES if (c.get("expect") or {}).get("interpreter", "rules") == "rules"]
OLLAMA_CASES = [c for c in CASES if (c.get("expect") or {}).get("interpreter") == "ollama"]


def _check_pref_expectation(
    prefs: PreferenceVector, key: str, bound: float, *, case_id: str
) -> None:
    if "_" not in key:
        raise AssertionError(f"{case_id}: preference key must be dim_gt|dim_lt, got {key}")
    dim, op = key.rsplit("_", 1)
    if dim not in PreferenceVector.model_fields:
        raise AssertionError(f"{case_id}: unknown preference dimension {dim!r} in {key}")
    value = getattr(prefs, dim)
    if op == "gt":
        assert value > bound, f"{case_id}: {dim}={value} expected > {bound}"
    elif op == "lt":
        assert value < bound, f"{case_id}: {dim}={value} expected < {bound}"
    else:
        raise AssertionError(f"{case_id}: unknown op in {key}")


def assert_golden_case(case: dict[str, Any], *, interpreter: str) -> None:
    expect = case.get("expect") or {}
    case_id = str(case["id"])
    intent = interpret_mission(
        case["prompt"],
        interpreter=interpreter,  # type: ignore[arg-type]
        repair_polarity=True,
    )

    if "days" in expect:
        assert intent.constraints.days == expect["days"], case_id
    if "origin" in expect:
        assert intent.constraints.origin == expect["origin"], case_id
    if "vehicle_contains" in expect:
        vehicle = intent.constraints.vehicle or ""
        assert expect["vehicle_contains"] in vehicle, case_id
    if "vehicle_class" in expect:
        assert intent.constraints.vehicle_class == expect["vehicle_class"], case_id
    if "party_size" in expect:
        assert intent.constraints.party_size == expect["party_size"], case_id
    if expect.get("near_neutral"):
        for dim, value in intent.preferences.as_dict().items():
            assert abs(value) < NEAR_NEUTRAL_ABS, (
                f"{case_id}: {dim}={value} expected near-neutral (|v|<{NEAR_NEUTRAL_ABS})"
            )
    for key, bound in (expect.get("preferences") or {}).items():
        _check_pref_expectation(intent.preferences, key, float(bound), case_id=case_id)


def test_golden_suite_size():
    assert len(CASES) >= 20, f"need ≥20 golden prompts, found {len(CASES)}"
    ids = [str(c["id"]) for c in CASES]
    assert len(ids) == len(set(ids)), (
        f"duplicate golden ids: {sorted({i for i in ids if ids.count(i) > 1})}"
    )
    inversion = [c for c in CASES if str(c["id"]).startswith("inv_")]
    assert len(inversion) >= 10, "keep ≥10 inv_* polarity cases"


@pytest.mark.parametrize("case", RULES_CASES, ids=lambda c: c["id"])
def test_golden_rules_sign_and_constraints(case: dict[str, Any]):
    assert_golden_case(case, interpreter="rules")


def test_golden_ollama_opt_in_gate():
    """Ollama goldens are opt-in; define cases with expect.interpreter: ollama."""
    if not OLLAMA_CASES:
        pytest.skip("no ollama golden cases defined yet")
    if os.environ.get("ADVENTURE_OLLAMA_GOLDENS", "").strip() not in {"1", "true", "yes"}:
        pytest.skip("set ADVENTURE_OLLAMA_GOLDENS=1 to run Ollama golden cases")
    for case in OLLAMA_CASES:
        assert_golden_case(case, interpreter="ollama")
