"""Preference polarity / inversion detection (issue #15)."""

from __future__ import annotations

import pytest
import yaml
from adventure_core.config import repo_root
from adventure_core.intent import PreferenceVector
from adventure_core.polarity import (
    detect_preference_inversions,
    repair_preference_inversions,
)
from adventure_inference.router import interpret_mission


def test_detects_hate_crowds_inversion():
    prefs = PreferenceVector(human_activity=0.9, solitude=-0.5)
    findings = detect_preference_inversions("I hate crowds", prefs)
    kinds = {(f.dimension, f.kind) for f in findings}
    assert ("human_activity", "inverted") in kinds


def test_repair_flips_inverted_human_activity():
    from adventure_core.intent import MissionIntent

    intent = MissionIntent(
        preferences=PreferenceVector(human_activity=0.8),
        source="llm",
    )
    fixed, findings = repair_preference_inversions(
        intent, prompt="Please avoid crowds this weekend."
    )
    assert findings
    assert fixed.preferences.human_activity < 0
    assert any(n.startswith("polarity_repair:") for n in fixed.interpreter_notes)


def test_repair_fills_missing_solitude():
    from adventure_core.intent import MissionIntent

    intent = MissionIntent(preferences=PreferenceVector(), source="llm")
    fixed, _ = repair_preference_inversions(intent, prompt="Seeking solitude away from people.")
    assert fixed.preferences.solitude > 0.3
    assert fixed.preferences.human_activity < -0.3


def test_love_crowds_not_treated_as_hate():
    prefs = PreferenceVector(human_activity=0.7)
    findings = detect_preference_inversions("I love crowds and nightlife", prefs)
    assert not any(f.kind == "inverted" for f in findings)


def test_hate_crowds_not_confused_with_love_rivers():
    """Regression: 'love rivers, hate crowds' must not match love_crowds."""
    intent = interpret_mission(
        "love rivers, hate crowds, don't want dangerous roads",
        interpreter="rules",
        repair_polarity=True,
    )
    assert intent.preferences.human_activity < -0.3
    assert intent.preferences.water > 0.3
    assert intent.preferences.danger < -0.3
    findings = detect_preference_inversions("love rivers, hate crowds", intent.preferences)
    assert not any(f.cue_id == "love_crowds" for f in findings)


def _check_pref_expectation(prefs: PreferenceVector, key: str, bound: float) -> None:
    dim, op = key.rsplit("_", 1)
    value = float(getattr(prefs, dim))
    if op == "gt":
        assert value > bound, f"{dim}={value} expected > {bound}"
    elif op == "lt":
        assert value < bound, f"{dim}={value} expected < {bound}"
    else:
        raise AssertionError(f"unknown op in {key}")


def test_golden_prompts_rules_polarity():
    path = repo_root() / "eval" / "golden_prompts.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    prompts = data["prompts"]
    assert len(prompts) >= 12

    inversion_cases = [p for p in prompts if str(p["id"]).startswith("inv_")]
    assert len(inversion_cases) >= 10

    for case in prompts:
        expect = case.get("expect") or {}
        if expect.get("interpreter", "rules") != "rules":
            continue
        intent = interpret_mission(case["prompt"], interpreter="rules", repair_polarity=True)
        if "days" in expect:
            assert intent.constraints.days == expect["days"]
        if "origin" in expect:
            assert intent.constraints.origin == expect["origin"]
        if "vehicle_contains" in expect:
            assert expect["vehicle_contains"] in (intent.constraints.vehicle or "")
        for key, bound in (expect.get("preferences") or {}).items():
            _check_pref_expectation(intent.preferences, key, float(bound))


def test_router_repairs_simulated_llm_inversion(monkeypatch: pytest.MonkeyPatch):
    import adventure_inference.router as router
    from adventure_core.intent import MissionIntent

    bad = MissionIntent(
        preferences=PreferenceVector(human_activity=0.9),
        source="llm",
    )

    monkeypatch.setattr(router, "ollama_available", lambda: True)
    monkeypatch.setattr(router, "interpret_ollama", lambda *a, **k: bad)

    intent = interpret_mission("I hate crowds", interpreter="ollama", repair_polarity=True)
    assert intent.preferences.human_activity < 0
    assert any("polarity_repair" in n for n in intent.interpreter_notes)
