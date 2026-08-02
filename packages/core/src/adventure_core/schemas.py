"""Pydantic schemas for the mission vertical slice."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from adventure_core.intent import HardConstraints, IntentCoverage, MissionIntent


class ReasonCode(BaseModel):
    code: str
    detail: str


class Confidence(BaseModel):
    """Heuristic claim confidence (pack-kind aware) — never pretend certainty."""

    value: float = Field(ge=0.0, le=1.0)
    reasons: list[ReasonCode] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class CandidateFeatures(BaseModel):
    remoteness: float = Field(ge=0.0, le=1.0)
    terrain_drama: float = Field(ge=0.0, le=1.0)
    water: float = Field(ge=0.0, le=1.0)
    viewpoint: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    access_fit: float = Field(ge=0.0, le=1.0)
    camping: float = Field(ge=0.0, le=1.0)
    forest: float = Field(ge=0.0, le=1.0)
    crowd: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)
    restriction: float = Field(ge=0.0, le=1.0)

    # None = layer missing / distance unknown (never use sentinel magics like -1 or 999)
    dist_settlement_km: float | None = None
    dist_road_km: float | None = None
    dist_water_km: float | None = None
    elevation_m: float = 0.0
    relief_m: float = 0.0

    # GIS depth (#23) — optional diagnostics; None when settlements/roads layer empty
    settlement_density: float | None = Field(default=None, ge=0.0, le=1.0)
    settlements_within_10km: int | None = Field(default=None, ge=0)
    nearest_highway: str | None = None


class Candidate(BaseModel):
    id: str
    name: str
    lon: float
    lat: float
    claim: str
    features: CandidateFeatures
    tags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class MissionRequest(BaseModel):
    prompt: str
    pack_id: str
    mode: str = "fearless_far"
    intent: MissionIntent = Field(default_factory=MissionIntent)
    max_results: int = 5

    @property
    def constraints(self) -> HardConstraints:
        return self.intent.constraints

    @property
    def days(self) -> float | None:
        return self.intent.constraints.days

    @property
    def vehicle(self) -> str | None:
        return self.intent.constraints.vehicle

    @property
    def party_size(self) -> int | None:
        return self.intent.constraints.party_size

    @property
    def budget_per_person(self) -> float | None:
        return self.intent.constraints.budget_per_person

    @property
    def currency(self) -> str | None:
        return self.intent.constraints.currency


class RankedMission(BaseModel):
    candidate_id: str
    name: str
    claim: str
    lon: float
    lat: float
    score: float
    confidence: Confidence
    feature_breakdown: dict[str, float]
    preference_adjustments: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class MissionResult(BaseModel):
    request: MissionRequest
    mode: str
    pack_id: str
    missions: list[RankedMission]
    coverage: IntentCoverage = Field(default_factory=IntentCoverage)
    notes: list[str] = Field(default_factory=list)
