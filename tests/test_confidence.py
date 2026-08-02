"""Pack-kind confidence gating and calibration metadata (issue #14)."""

from __future__ import annotations

from adventure_core.schemas import Candidate, CandidateFeatures
from adventure_scoring.confidence import (
    CALIBRATION_VERSION,
    REAL_CONFIDENCE_CEILING,
    SYNTHETIC_CONFIDENCE_CEILING,
    apply_calibration_hook,
    build_confidence,
    resolve_pack_kind,
)


def _strong_candidate(*, evidence: dict | None = None) -> Candidate:
    """Features strong enough to saturate the real-pack noisy-OR near the ceiling."""
    return Candidate(
        id="c1",
        name="Strong multi-channel seed",
        lon=75.5,
        lat=35.4,
        claim="test claim",
        features=CandidateFeatures(
            remoteness=0.9,
            terrain_drama=0.8,
            water=0.9,
            viewpoint=0.7,
            novelty=0.8,
            access_fit=0.7,
            camping=0.4,
            forest=0.3,
            crowd=0.1,
            risk=0.1,
            restriction=0.0,
            dist_settlement_km=25.0,
            dist_road_km=2.0,
            dist_water_km=0.5,
            elevation_m=3200.0,
            relief_m=800.0,
        ),
        evidence=evidence or {"source": "osm+dem", "generator": "named_waterbody"},
    )


def test_synthetic_ceiling_below_real_for_identical_features() -> None:
    cand = _strong_candidate()
    real = build_confidence(cand, pack_synthetic=False)
    synth = build_confidence(cand, pack_synthetic=True)
    assert real.value > synth.value
    assert real.value <= REAL_CONFIDENCE_CEILING
    assert synth.value <= SYNTHETIC_CONFIDENCE_CEILING
    assert synth.value < 0.85  # must not claim “high” like real packs
    assert "synthetic_pack_confidence_ceiling" in synth.uncertainties
    assert "sensor_and_map_resolution_limits" in real.uncertainties
    assert "confidence_not_empirically_calibrated" in real.uncertainties
    assert "confidence_not_empirically_calibrated" in synth.uncertainties


def test_pack_kind_overrides_feature_heuristic() -> None:
    # Feature evidence looks synthetic, but pack says real → real priors
    cand = _strong_candidate(
        evidence={
            "source": "synthetic",
            "generator": "synthetic_fixture",
            "provenance": {"sources": ["synthetic"]},
        }
    )
    assert resolve_pack_kind(cand, pack_synthetic=False) == "real"
    conf = build_confidence(cand, pack_synthetic=False)
    assert conf.value > SYNTHETIC_CONFIDENCE_CEILING
    assert "synthetic_pack_confidence_ceiling" not in conf.uncertainties


def test_feature_heuristic_when_pack_kind_omitted() -> None:
    synth_ev = _strong_candidate(evidence={"source": "synthetic", "generator": "named_waterbody"})
    real_ev = _strong_candidate(evidence={"source": "osm", "generator": "named_waterbody"})
    assert resolve_pack_kind(synth_ev) == "synthetic"
    assert resolve_pack_kind(real_ev) == "real"
    assert build_confidence(synth_ev).value <= SYNTHETIC_CONFIDENCE_CEILING
    assert build_confidence(real_ev).value > SYNTHETIC_CONFIDENCE_CEILING


def test_calibration_hook_is_identity() -> None:
    cand = _strong_candidate()
    base = build_confidence(cand, pack_synthetic=True)
    hooked = apply_calibration_hook(base, pack_kind="synthetic")
    assert hooked.model_dump() == base.model_dump()


def test_strong_candidates_saturate_pack_ceilings() -> None:
    cand = _strong_candidate()
    assert build_confidence(cand, pack_synthetic=False).value == REAL_CONFIDENCE_CEILING
    assert build_confidence(cand, pack_synthetic=True).value == SYNTHETIC_CONFIDENCE_CEILING


def test_weak_evidence_scales_and_keeps_uncertainty_tags() -> None:
    weak = Candidate(
        id="w1",
        name="weak",
        lon=75.0,
        lat=35.0,
        claim="weak claim",
        features=CandidateFeatures(
            remoteness=0.1,
            terrain_drama=0.1,
            water=0.1,
            viewpoint=0.1,
            novelty=0.1,
            access_fit=0.2,
            camping=0.1,
            forest=0.1,
            crowd=0.4,
            risk=0.7,
            restriction=0.6,
            dist_settlement_km=2.0,
            dist_road_km=0.5,
            dist_water_km=8.0,
        ),
        evidence={"source": "osm"},
    )
    real = build_confidence(weak, pack_synthetic=False)
    synth = build_confidence(weak, pack_synthetic=True)
    assert "few_independent_evidence_channels" in real.uncertainties
    assert "elevated_hazard_flags" in real.uncertainties
    assert "protected_or_restricted_area" in real.uncertainties
    assert synth.value < real.value
    assert synth.value == round(0.25 * 0.75 * 0.85 * 0.8, 3)


def test_rank_missions_applies_pack_synthetic_ceiling() -> None:
    from adventure_core.config import load_mode
    from adventure_core.intent import MissionIntent
    from adventure_scoring import rank_missions

    mode = load_mode("fearless_far")
    cand = _strong_candidate()
    real = rank_missions([cand], mode, intent=MissionIntent(), max_results=1, pack_synthetic=False)
    synth = rank_missions([cand], mode, intent=MissionIntent(), max_results=1, pack_synthetic=True)
    assert real and synth
    assert real[0].confidence.value == REAL_CONFIDENCE_CEILING
    assert synth[0].confidence.value == SYNTHETIC_CONFIDENCE_CEILING


def test_mission_notes_expose_calibration_version() -> None:
    from adventure_cli.pipeline import run_mission

    result = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt="quiet lakes away from crowds",
        max_results=3,
        interpreter="rules",
    )
    assert f"confidence_calibration={CALIBRATION_VERSION}" in result.notes
    assert "pack_kind=synthetic" in result.notes
    assert "synthetic=True" in result.notes
    assert result.missions
    for m in result.missions:
        assert m.confidence.value <= SYNTHETIC_CONFIDENCE_CEILING
        assert "synthetic_pack_confidence_ceiling" in m.confidence.uncertainties
        assert "confidence_not_empirically_calibrated" in m.confidence.uncertainties
