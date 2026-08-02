"""Frozen concept → preference-dimension ontology.

Rule interpreters may use this map. New natural-language phrasing should go
through the LLM Mission Interpreter — do NOT keep expanding phrase lists here.
"""

from __future__ import annotations

# concept_id → {dimension: weight in [-1, 1]}
CONCEPT_TO_DIMENSIONS: dict[str, dict[str, float]] = {
    # Water family
    "water": {"water": 0.9, "beauty": 0.2},
    "river": {"water": 0.95, "beauty": 0.25},
    "lake": {"water": 0.9, "beauty": 0.35, "photography": 0.2},
    "waterfall": {"water": 0.85, "beauty": 0.5, "photography": 0.4},
    # Vegetation
    "forest": {"forest": 0.95, "wildlife": 0.3, "solitude": 0.2},
    "vegetation": {"forest": 0.7},
    # Remoteness / crowds
    "remote": {"remoteness": 0.9, "novelty": 0.4, "solitude": 0.5, "human_activity": -0.4},
    "solitude": {"solitude": 0.9, "human_activity": -0.7, "novelty": 0.3},
    "crowds": {"human_activity": 0.9, "solitude": -0.7},  # "want crowds" rare; avoid flips sign
    "quiet": {"solitude": 0.8, "human_activity": -0.6},
    # Scenic
    "scenic": {"beauty": 0.85, "photography": 0.6},
    "viewpoint": {"photography": 0.9, "beauty": 0.7, "geology": 0.3},
    "magical": {"novelty": 0.7, "beauty": 0.85, "human_activity": -0.5, "photography": 0.4},
    "untouched": {"novelty": 0.95, "human_activity": -0.85, "remoteness": 0.7, "beauty": 0.5},
    # Safety / access
    "danger": {"danger": 0.8, "accessibility": -0.3},
    "safe_roads": {"danger": -0.85, "accessibility": 0.55},
    "easy_access": {"accessibility": 0.8, "hiking": -0.2},
    # Activities
    "camping": {"camping": 0.9, "accessibility": 0.2},
    "hiking": {"hiking": 0.9, "remoteness": 0.3},
    "history": {"history": 0.9, "novelty": 0.2},
    "wildlife": {"wildlife": 0.9, "forest": 0.4, "solitude": 0.3},
    "geology": {"geology": 0.9, "beauty": 0.3},
    "surprise": {"novelty": 0.55, "remoteness": 0.25},
}


def apply_concept(
    prefs: dict[str, float],
    concept: str,
    *,
    strength: float = 1.0,
    invert: bool = False,
) -> dict[str, float]:
    """Merge a concept into a preference dict. strength in [0, 1]."""
    dims = CONCEPT_TO_DIMENSIONS.get(concept)
    if not dims:
        return prefs
    sign = -1.0 if invert else 1.0
    out = dict(prefs)
    for dim, w in dims.items():
        delta = sign * float(w) * max(0.0, min(1.0, strength))
        out[dim] = max(-1.0, min(1.0, out.get(dim, 0.0) + delta))
    return out
