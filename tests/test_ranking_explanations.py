"""Deterministic ranking explanations (RFC-0009 / #27)."""

from __future__ import annotations

from adventure_core.config import load_mode
from adventure_core.intent import MissionIntent, PreferenceVector
from adventure_core.schemas import Candidate, CandidateFeatures
from adventure_scoring.explanations import build_ranking_explanations
from adventure_scoring.scorer import rank_missions, score_candidate


def _cand(**kwargs) -> Candidate:
    feats = CandidateFeatures(
        remoteness=kwargs.pop("remoteness", 0.8),
        terrain_drama=kwargs.pop("terrain_drama", 0.5),
        water=kwargs.pop("water", 0.9),
        viewpoint=kwargs.pop("viewpoint", 0.2),
        novelty=kwargs.pop("novelty", 0.7),
        access_fit=kwargs.pop("access_fit", 0.6),
        camping=kwargs.pop("camping", 0.3),
        forest=kwargs.pop("forest", 0.4),
        crowd=kwargs.pop("crowd", 0.1),
        risk=kwargs.pop("risk", 0.2),
        restriction=kwargs.pop("restriction", 0.0),
    )
    return Candidate(
        id=kwargs.pop("id", "c1"),
        name=kwargs.pop("name", "Test Lake"),
        lon=75.0,
        lat=35.5,
        claim="remote lake",
        features=feats,
        tags=kwargs.pop("tags", ["lake", "water"]),
        evidence=kwargs.pop(
            "evidence", {"generator": "named_waterbody", "ontology_ids": ["water.lake"]}
        ),
    )


def test_build_ranking_explanations_pref_and_evidence():
    reasons = build_ranking_explanations(
        feature_breakdown={
            "water": 0.25,
            "remoteness": 0.2,
            "terrain_drama": 0.01,
            "viewpoint": 0.0,
            "novelty": 0.1,
            "access_fit": 0.05,
            "camping": 0.0,
            "risk_factor": 0.9,
            "preference_factor": 1.4,
        },
        preference_adjustments={
            "water": 0.72,
            "remoteness": 0.3,
            "_alignment": 0.8,
            "_factor": 1.4,
            "goal_factor": 1.05,
            "origin_travel": -0.3,
            "origin_one_way_hours": 9.5,
        },
        evidence={"generator": "named_waterbody", "ontology_ids": ["water.lake"]},
        max_reasons=6,
    )
    codes = [r.code for r in reasons]
    # Prefs / constraints before drowning in mode lines
    assert codes.index("constraint.origin_travel") < codes.index("mode.water")
    assert codes.index("pref.water") < codes.index("mode.water")
    assert "evidence.generator" in codes
    assert any("matches water" in r.detail for r in reasons)
    assert any("travel-time" in r.detail for r in reasons)
    assert len(reasons) <= 6


def test_prefs_not_hidden_by_large_mode_priors():
    reasons = build_ranking_explanations(
        feature_breakdown={
            "novelty": 1.4,
            "remoteness": 1.3,
            "terrain_drama": 1.2,
            "water": 1.0,
            "viewpoint": 0.9,
            "camping": 0.8,
        },
        preference_adjustments={"water": 0.7, "human_activity": -0.5},
        evidence={"generator": "named_waterbody"},
        max_reasons=6,
    )
    codes = [r.code for r in reasons]
    assert "pref.water" in codes
    assert "pref.human_activity" in codes
    assert codes.index("pref.water") < codes.index("mode.novelty")


def test_explanations_skip_noise():
    reasons = build_ranking_explanations(
        feature_breakdown={"water": 0.01, "remoteness": 0.0},
        preference_adjustments={"water": 0.01, "goal_factor": 1.0},
        evidence={},
    )
    assert reasons == [] or all(not c.startswith("pref.") for c in [r.code for r in reasons])


def test_rank_missions_attaches_explanations():
    mode = load_mode("fearless_far")
    intent = MissionIntent(
        preferences=PreferenceVector(water=0.9, remoteness=0.5),
        goals=["discovery"],
        source="rules",
    )
    ranked = rank_missions(
        [_cand()],
        mode,
        intent=intent,
        max_results=1,
        pack_synthetic=True,
        min_confidence=0.0,
    )
    assert ranked
    assert ranked[0].explanations
    assert any(
        r.code.startswith("pref.") or r.code.startswith("mode.") for r in ranked[0].explanations
    )
    assert any(r.code == "evidence.generator" for r in ranked[0].explanations)


def test_explanations_do_not_change_score():
    mode = load_mode("fearless_far")
    intent = MissionIntent(preferences=PreferenceVector(water=0.8), source="rules")
    cand = _cand()
    score, breakdown, adj = score_candidate(cand, mode, intent)
    reasons = build_ranking_explanations(
        feature_breakdown=breakdown,
        preference_adjustments=adj,
        evidence=cand.evidence,
    )
    score2, _, _ = score_candidate(cand, mode, intent)
    assert score == score2
    assert reasons  # smoke: builders run independently of score
