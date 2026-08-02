"""Adventure scoring and confidence calibration."""

from adventure_scoring.confidence import (
    CALIBRATION_VERSION,
    apply_calibration_hook,
    build_confidence,
)
from adventure_scoring.explanations import build_ranking_explanations
from adventure_scoring.scorer import (
    build_intent_coverage,
    candidate_dimensions,
    preference_alignment,
    rank_missions,
    score_candidate,
)

__all__ = [
    "CALIBRATION_VERSION",
    "apply_calibration_hook",
    "score_candidate",
    "rank_missions",
    "build_confidence",
    "build_intent_coverage",
    "build_ranking_explanations",
    "candidate_dimensions",
    "preference_alignment",
]
