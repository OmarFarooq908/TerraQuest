"""Deterministic ranking explanations (RFC-0009 / #27)."""

from __future__ import annotations

from adventure_core.config import load_mode
from adventure_core.intent import MissionIntent, PreferenceVector
from adventure_core.schemas import Candidate, CandidateFeatures
from adventure_scoring.explanations import build_ranking_explanations
from adventure_scoring.scorer import candidate_dimensions, rank_missions, score_candidate


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
        preference_weights={"water": 0.9, "remoteness": 0.5},
        dimensions={"water": 0.8, "remoteness": 0.6},
        max_reasons=6,
    )
    codes = [r.code for r in reasons]
    assert "constraint.origin_travel" in codes
    assert "pref.water" in codes
    # With two evidence slots reserved, mode lines may be squeezed out — that's OK.
    assert "evidence.generator" in codes
    assert "evidence.ontology" in codes
    assert any("matches water" in r.detail for r in reasons)
    assert any("travel-time" in r.detail for r in reasons)
    assert len(reasons) <= 6
    # Prefs / constraints appear before any mode lines that remain
    mode_idxs = [i for i, c in enumerate(codes) if c.startswith("mode.")]
    if mode_idxs:
        assert codes.index("pref.water") < mode_idxs[0]
        assert codes.index("constraint.origin_travel") < mode_idxs[0]


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
        preference_weights={"water": 0.9, "human_activity": -0.9},
        dimensions={"water": 0.8, "human_activity": 0.9},
        max_reasons=6,
    )
    codes = [r.code for r in reasons]
    assert "pref.water" in codes
    assert "pref.human_activity" in codes
    assert codes.index("pref.water") < codes.index("mode.novelty")
    assert any("higher human_activity" in r.detail for r in reasons)


def test_avoid_pref_on_quiet_place_is_not_conflict():
    """Negative preference × low feature must not say 'conflicts'."""
    reasons = build_ranking_explanations(
        feature_breakdown={"water": 0.5, "remoteness": 0.4},
        preference_adjustments={"human_activity": -0.045, "water": 0.8, "solitude": 0.7},
        evidence={"generator": "named_waterbody"},
        preference_weights={"human_activity": -0.9, "water": 0.9, "solitude": 0.8},
        dimensions={"human_activity": 0.05, "water": 0.9, "solitude": 0.95},
        max_reasons=6,
    )
    ha = next(r for r in reasons if r.code == "pref.human_activity")
    assert "honors avoid-human_activity" in ha.detail
    assert "conflicts" not in ha.detail


def test_explanations_skip_noise():
    reasons = build_ranking_explanations(
        feature_breakdown={"water": 0.01, "remoteness": 0.0},
        preference_adjustments={"water": 0.01, "goal_factor": 1.0},
        evidence={},
    )
    assert reasons == []


def test_max_reasons_zero():
    assert (
        build_ranking_explanations(
            feature_breakdown={"water": 1.0},
            preference_adjustments={"water": 0.5},
            max_reasons=0,
        )
        == []
    )


def test_rank_missions_attaches_explanations():
    mode = load_mode("fearless_far")
    intent = MissionIntent(
        preferences=PreferenceVector(water=0.9, remoteness=0.5, human_activity=-0.8),
        goals=["discovery"],
        source="rules",
    )
    ranked = rank_missions(
        [_cand(crowd=0.05)],
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
    ha = [r for r in ranked[0].explanations if r.code == "pref.human_activity"]
    if ha:
        assert "conflicts" not in ha[0].detail
        assert "honors" in ha[0].detail or "avoid" in ha[0].detail


def test_explanations_do_not_change_score():
    mode = load_mode("fearless_far")
    intent = MissionIntent(preferences=PreferenceVector(water=0.8), source="rules")
    cand = _cand()
    score, breakdown, adj = score_candidate(cand, mode, intent)
    dims = candidate_dimensions(cand)
    reasons = build_ranking_explanations(
        feature_breakdown=breakdown,
        preference_adjustments=adj,
        evidence=cand.evidence,
        preference_weights=intent.preferences.active(),
        dimensions=dims,
    )
    score2, _, _ = score_candidate(cand, mode, intent)
    assert score == score2
    assert reasons
