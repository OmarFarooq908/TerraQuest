"""Deterministic scoring over MissionIntent preference vectors.

The scorer never reads prompt text — only MissionIntent + candidate features.
"""

from __future__ import annotations

from adventure_core.config import ModeWeights
from adventure_core.constraints import estimate_one_way_hours
from adventure_core.geo import Point
from adventure_core.intent import (
    PREFERENCE_DIMENSIONS,
    HardConstraints,
    IntentCoverage,
    IntentCoverageField,
    MissionIntent,
    PreferenceVector,
)
from adventure_core.schemas import Candidate, RankedMission

from adventure_scoring.confidence import build_confidence


def candidate_dimensions(candidate: Candidate) -> dict[str, float]:
    """Project GIS features into the same latent space as preferences."""
    f = candidate.features
    tags = set(candidate.tags)
    history = 0.85 if ("history" in tags or "pasture" in tags) else 0.05
    if candidate.evidence.get("kind") == "shepherd_settlement":
        history = max(history, 0.8)

    beauty = max(0.0, min(1.0, 0.4 * f.viewpoint + 0.35 * f.terrain_drama + 0.25 * f.water))
    wildlife = max(0.0, min(1.0, 0.55 * f.forest + 0.45 * f.remoteness))
    hiking = max(0.0, min(1.0, 0.5 * f.remoteness + 0.5 * (1.0 - f.access_fit)))
    solitude = max(0.0, min(1.0, 1.0 - f.crowd))

    return {
        "beauty": beauty,
        "water": f.water,
        "forest": f.forest,
        "geology": f.terrain_drama,
        "wildlife": wildlife,
        "remoteness": f.remoteness,
        "accessibility": f.access_fit,
        "novelty": f.novelty,
        "photography": f.viewpoint,
        "danger": f.risk,
        "solitude": solitude,
        "hiking": hiking,
        "camping": f.camping,
        "history": history,
        "human_activity": f.crowd,
    }


def preference_alignment(
    preferences: PreferenceVector,
    dimensions: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """Return multiplicative factor from preference↔candidate alignment.

    When many dimensions are active (rich prompt), amplify the factor so the
    preference vector can outweigh the discovery-mode base prior.
    """
    active = preferences.active()
    if not active:
        return 1.0, {}

    weighted = 0.0
    denom = 0.0
    per_dim: dict[str, float] = {}
    for dim, weight in active.items():
        x = float(dimensions.get(dim, 0.0))
        contrib = weight * x
        per_dim[dim] = round(contrib, 4)
        weighted += contrib
        denom += abs(weight)

    alignment = weighted / denom if denom else 0.0  # [-1, 1]
    # Richer intents (more |weight| mass) get stronger preference authority
    strength = min(1.0, denom / 2.5)
    gain = 0.85 + 1.1 * strength
    factor = max(0.12, 1.0 + gain * alignment)
    per_dim["_alignment"] = round(alignment, 4)
    per_dim["_pref_strength"] = round(strength, 4)
    per_dim["_factor"] = round(factor, 4)
    return factor, per_dim


def hard_constraint_factor(
    candidate: Candidate,
    constraints: HardConstraints,
) -> tuple[float, dict[str, float]]:
    """Structural logistics penalties (travel window, tight budget)."""
    factor = 1.0
    adj: dict[str, float] = {}
    f = candidate.features

    if constraints.origin_lon is not None and constraints.origin_lat is not None:
        if constraints.days is not None:
            origin = Point(constraints.origin_lon, constraints.origin_lat)
            hours = estimate_one_way_hours(origin, Point(candidate.lon, candidate.lat))
            budget_h = 6.0 if constraints.days <= 2.5 else (8.0 if constraints.days <= 3 else 12.0)
            if hours > budget_h:
                over = (hours - budget_h) / budget_h
                penalty = min(0.7, 0.25 + 0.35 * over)
                factor *= 1.0 - penalty
                adj["origin_travel"] = round(-penalty, 4)
            else:
                adj["origin_travel"] = 0.0
            adj["origin_one_way_hours"] = round(hours, 2)

    if constraints.budget_per_person is not None and constraints.budget_per_person < 18000:
        boost = 0.08 * f.access_fit - 0.05 * (1.0 - f.access_fit)
        factor *= 1.0 + boost
        adj["budget_access_nudge"] = round(boost, 4)

    # Strong negative danger preference is also in vector; extra hard floor when danger pref << 0
    return max(0.05, factor), adj


def goal_factor(candidate: Candidate, goals: list[str], dimensions: dict[str, float]) -> float:
    if not goals:
        return 1.0
    boost = 0.0
    if "discovery" in goals:
        boost += 0.08 * dimensions["novelty"]
    if "photography" in goals:
        boost += 0.10 * dimensions["photography"]
    if "camping" in goals:
        boost += 0.08 * dimensions["camping"]
    if "hiking" in goals:
        boost += 0.08 * dimensions["hiking"]
    if "history" in goals:
        boost += 0.10 * dimensions["history"]
    if "wildlife" in goals:
        boost += 0.10 * dimensions["wildlife"]
    if "surprise" in goals:
        boost += 0.06 * dimensions["novelty"]
    return 1.0 + boost / max(1, len(goals))


def _passes_gates(candidate: Candidate, mode: ModeWeights) -> bool:
    if not mode.gates:
        return True
    values = candidate.features.model_dump()
    for key, minimum in mode.gates.items():
        if float(values.get(key, 0.0)) < float(minimum):
            return False
    return True


def score_candidate(
    candidate: Candidate,
    mode: ModeWeights,
    intent: MissionIntent,
) -> tuple[float, dict[str, float], dict[str, float]]:
    """Mode prior × preference alignment × hard constraints × goals."""
    dims = candidate_dimensions(candidate)
    f = candidate.features

    # Mode weights still provide a base adventure prior over classic features
    classic = {
        "remoteness": f.remoteness,
        "terrain_drama": f.terrain_drama,
        "water": f.water,
        "viewpoint": f.viewpoint,
        "novelty": f.novelty,
        "access_fit": f.access_fit,
        "camping": f.camping,
    }
    weighted_sum = 0.0
    weight_total = 0.0
    breakdown: dict[str, float] = {}
    for key, val in classic.items():
        w = float(mode.weights.get(key, 0.0))
        breakdown[key] = round(w * val, 4)
        weighted_sum += w * val
        weight_total += abs(w)
    raw = weighted_sum / weight_total if weight_total else 0.0

    risk_weight = mode.risk_weight
    # If user wants low danger, amplify risk penalty in base
    if intent.preferences.danger <= -0.4:
        risk_weight *= 1.35

    risk_factor = max(0.25, 1.0 - 0.45 * risk_weight * f.risk)
    restriction_factor = max(0.25, 1.0 - 0.45 * mode.restriction_weight * f.restriction)
    coherence = 0.35 + 0.65 * ((f.remoteness + f.novelty) / 2.0)
    base = raw * risk_factor * restriction_factor * coherence

    pref_factor, pref_adj = preference_alignment(intent.preferences, dims)
    hard_f, hard_adj = hard_constraint_factor(candidate, intent.constraints)
    g_factor = goal_factor(candidate, intent.goals, dims)

    score = max(0.0, base * pref_factor * hard_f * g_factor)
    breakdown["risk_factor"] = round(risk_factor, 4)
    breakdown["restriction_factor"] = round(restriction_factor, 4)
    breakdown["coherence"] = round(coherence, 4)
    breakdown["preference_factor"] = round(pref_factor, 4)
    breakdown["hard_constraint_factor"] = round(hard_f, 4)
    breakdown["goal_factor"] = round(g_factor, 4)

    adjustments = {**pref_adj, **hard_adj, "goal_factor": round(g_factor, 4)}
    return round(score, 4), breakdown, adjustments


def build_intent_coverage(intent: MissionIntent) -> IntentCoverage:
    c = intent.constraints
    p = intent.preferences.active()
    fields: list[IntentCoverageField] = [
        IntentCoverageField(
            field="schema_version",
            present=True,
            value=intent.schema_version,
            role="meta",
            scoring="used",
            reason="stable MissionIntent contract",
        ),
        IntentCoverageField(
            field="interpreter",
            present=True,
            value=intent.source,
            role="meta",
            scoring="used",
            reason="; ".join(intent.interpreter_notes) or intent.source,
        ),
        IntentCoverageField(
            field="vehicle",
            present=c.vehicle is not None,
            value=c.vehicle,
            role="constraint",
            scoring="used" if c.vehicle else "neutral",
            reason="modulates GIS access_fit" if c.vehicle else "unspecified",
        ),
        IntentCoverageField(
            field="days",
            present=c.days is not None,
            value=c.days,
            role="constraint",
            scoring="used" if c.days is not None else "neutral",
            reason="travel window + access_fit" if c.days is not None else "unspecified",
        ),
        IntentCoverageField(
            field="origin",
            present=c.origin is not None,
            value=c.origin,
            role="constraint",
            scoring="used" if c.origin else "neutral",
            reason="one-way hours vs days budget" if c.origin else "unspecified",
        ),
        IntentCoverageField(
            field="budget",
            present=c.budget_per_person is not None,
            value={"amount": c.budget_per_person, "currency": c.currency},
            role="constraint",
            scoring="partial" if c.budget_per_person is not None else "neutral",
            reason="soft access nudge only",
        ),
        IntentCoverageField(
            field="party_size",
            present=c.party_size is not None,
            value=c.party_size,
            role="constraint",
            scoring="ignored" if c.party_size is not None else "neutral",
            reason="camping capacity model not implemented",
        ),
        IntentCoverageField(
            field="preference_vector",
            present=bool(p),
            value=p,
            role="preference",
            scoring="used" if p else "neutral",
            reason="dot-aligned against candidate dimensions" if p else "empty vector",
        ),
        IntentCoverageField(
            field="goals",
            present=bool(intent.goals),
            value=intent.goals,
            role="goal",
            scoring="used" if intent.goals else "neutral",
            reason="goal_factor over matching dimensions",
        ),
    ]
    for dim in PREFERENCE_DIMENSIONS:
        val = getattr(intent.preferences, dim)
        if abs(val) < 0.05:
            continue
        fields.append(
            IntentCoverageField(
                field=f"pref.{dim}",
                present=True,
                value=val,
                role="preference",
                scoring="used",
                reason="preference_alignment",
            )
        )
    return IntentCoverage(fields=fields, interpreter=intent.source)


def rank_missions(
    candidates: list[Candidate],
    mode: ModeWeights,
    *,
    intent: MissionIntent,
    max_results: int = 5,
    min_confidence: float = 0.35,
    pack_synthetic: bool | None = None,
) -> list[RankedMission]:
    ranked: list[RankedMission] = []
    for cand in candidates:
        if not _passes_gates(cand, mode):
            continue
        score, breakdown, adj = score_candidate(cand, mode, intent)
        conf = build_confidence(cand, pack_synthetic=pack_synthetic)
        if conf.value < min_confidence:
            continue
        ranked.append(
            RankedMission(
                candidate_id=cand.id,
                name=cand.name,
                claim=cand.claim,
                lon=cand.lon,
                lat=cand.lat,
                score=score,
                confidence=conf,
                feature_breakdown=breakdown,
                preference_adjustments=adj,
                tags=cand.tags,
                evidence={
                    **cand.evidence,
                    "dimensions": candidate_dimensions(cand),
                },
            )
        )
    ranked.sort(key=lambda m: (m.score, m.confidence.value), reverse=True)

    diversified: list[RankedMission] = []
    seen_kinds: set[str] = set()
    for m in ranked:
        kind = next(
            (t for t in m.tags if t not in {"fearless", "far", "control"}),
            m.candidate_id,
        )
        if kind in seen_kinds and len(diversified) >= 2:
            continue
        seen_kinds.add(kind)
        diversified.append(m)
        if len(diversified) >= max_results:
            break

    if len(diversified) < min(max_results, len(ranked)):
        ids = {m.candidate_id for m in diversified}
        for m in ranked:
            if m.candidate_id not in ids:
                diversified.append(m)
            if len(diversified) >= max_results:
                break

    return diversified


# Back-compat shim names used by older imports during transition
def scoring_impact_map(intent: MissionIntent) -> dict:
    return {"intent": ("used", "preference vector scoring")}
