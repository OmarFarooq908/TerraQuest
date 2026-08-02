"""Versioned Mission Intent: hard constraints + preference vector + goals.

The scorer consumes this schema — never raw prompt text.
New user phrasing should improve the *interpreter*, not the scoring engine.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "1.0"

# Latent preference space — fixed dimensions. Interpreters map language → these.
PREFERENCE_DIMENSIONS: tuple[str, ...] = (
    "beauty",
    "water",
    "forest",
    "geology",
    "wildlife",
    "remoteness",
    "accessibility",
    "novelty",
    "photography",
    "danger",  # positive = seek challenge; negative = avoid hazard
    "solitude",
    "hiking",
    "camping",
    "history",
    "human_activity",  # positive = lively; negative = hate crowds
)

GoalId = Literal[
    "discovery",
    "photography",
    "camping",
    "hiking",
    "history",
    "wildlife",
    "relaxation",
    "surprise",
]


class HardConstraints(BaseModel):
    """Hard logistics — must be respected, not softly preferred."""

    days: float | None = None
    vehicle: str | None = None
    vehicle_class: str | None = None
    party_size: int | None = None
    budget_per_person: float | None = None
    currency: str | None = None
    origin: str | None = None
    origin_lon: float | None = None
    origin_lat: float | None = None
    departure: str | None = None
    return_by: str | None = None


class PreferenceVector(BaseModel):
    """Soft preferences in [-1, 1]. 0 = neutral / unspecified.

    Positive = want more of this dimension.
    Negative = want less (e.g. human_activity=-0.9 for hate crowds).
    """

    beauty: float = 0.0
    water: float = 0.0
    forest: float = 0.0
    geology: float = 0.0
    wildlife: float = 0.0
    remoteness: float = 0.0
    accessibility: float = 0.0
    novelty: float = 0.0
    photography: float = 0.0
    danger: float = 0.0
    solitude: float = 0.0
    hiking: float = 0.0
    camping: float = 0.0
    history: float = 0.0
    human_activity: float = 0.0

    @field_validator("*")
    @classmethod
    def _clip(cls, v: float) -> float:
        return max(-1.0, min(1.0, float(v)))

    def as_dict(self) -> dict[str, float]:
        return {d: float(getattr(self, d)) for d in PREFERENCE_DIMENSIONS}

    def active(self) -> dict[str, float]:
        return {k: v for k, v in self.as_dict().items() if abs(v) >= 0.05}

    def is_empty(self) -> bool:
        return not self.active()


class MissionIntent(BaseModel):
    """Stable contract between language understanding and the mission engine."""

    schema_version: str = SCHEMA_VERSION
    constraints: HardConstraints = Field(default_factory=HardConstraints)
    preferences: PreferenceVector = Field(default_factory=PreferenceVector)
    goals: list[str] = Field(default_factory=list)
    source: Literal["rules", "llm", "hybrid"] = "rules"
    interpreter_notes: list[str] = Field(default_factory=list)
    raw_prompt: str | None = None

    def merge_mode_prior(self, mode_id: str) -> MissionIntent:
        """Apply discovery-mode prior as weak preference defaults (non-destructive)."""
        priors: dict[str, dict[str, float]] = {
            "explorer": {"novelty": 0.7, "remoteness": 0.6, "solitude": 0.4},
            "lost_world": {"novelty": 0.85, "remoteness": 0.7, "human_activity": -0.6},
            "photographer": {"photography": 0.85, "beauty": 0.7, "water": 0.3},
            "survival": {"water": 0.7, "camping": 0.7, "danger": -0.6, "accessibility": 0.5},
            "history": {"history": 0.8, "novelty": 0.3},
            "wildlife": {"wildlife": 0.8, "forest": 0.5, "solitude": 0.4},
            "fearless_far": {
                "novelty": 0.55,
                "remoteness": 0.5,
                "beauty": 0.35,
                "accessibility": 0.35,
                "camping": 0.25,
            },
        }
        prior = priors.get(mode_id, {})
        prefs = self.preferences.model_copy()
        for dim, value in prior.items():
            current = getattr(prefs, dim)
            if abs(current) < 0.05:
                setattr(prefs, dim, value)
        return self.model_copy(update={"preferences": prefs})


class IntentCoverageField(BaseModel):
    field: str
    present: bool
    value: Any = None
    role: Literal["constraint", "preference", "goal", "meta"]
    scoring: Literal["used", "partial", "ignored", "neutral"]
    reason: str


class IntentCoverage(BaseModel):
    fields: list[IntentCoverageField] = Field(default_factory=list)
    interpreter: str = "rules"
    schema_version: str = SCHEMA_VERSION
