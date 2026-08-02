"""Mission interpreters: language → MissionIntent (never picks winners)."""

from __future__ import annotations

from adventure_core.constraints import MissionConstraints, parse_constraints
from adventure_core.intent import HardConstraints, MissionIntent, PreferenceVector
from adventure_core.ontology import apply_concept


def constraints_to_hard(c: MissionConstraints) -> HardConstraints:
    return HardConstraints(
        days=c.days,
        vehicle=c.vehicle,
        vehicle_class=c.vehicle_class,
        party_size=c.party_size,
        budget_per_person=c.budget_per_person,
        currency=c.currency,
        origin=c.origin,
        origin_lon=c.origin_lon,
        origin_lat=c.origin_lat,
        departure=c.departure,
        return_by=c.return_by,
    )


def legacy_constraints_to_preferences(c: MissionConstraints) -> PreferenceVector:
    """Map legacy prefer/avoid lists through the ontology (no new phrase rules)."""
    prefs: dict[str, float] = {}

    concept_map = {
        "rivers": ("river", False),
        "forests": ("forest", False),
        "lakes": ("lake", False),
        "viewpoints": ("viewpoint", False),
        "remote": ("remote", False),
    }
    for item in c.prefer:
        mapped = concept_map.get(item)
        if mapped:
            prefs = apply_concept(prefs, mapped[0], strength=0.9, invert=mapped[1])

    avoid_map = {
        "crowds": ("crowds", True),  # invert crowds concept → negative human_activity
        "dangerous_roads": ("safe_roads", False),  # seeking safe roads
    }
    for item in c.avoid:
        mapped = avoid_map.get(item)
        if mapped:
            prefs = apply_concept(prefs, mapped[0], strength=0.9, invert=mapped[1])

    for style in c.style:
        if style == "surprise":
            prefs = apply_concept(prefs, "surprise", strength=0.7)
        if style == "fearless_far":
            prefs = apply_concept(prefs, "remote", strength=0.5)
            prefs = apply_concept(prefs, "untouched", strength=0.4)

    # If avoid crowds was stored as invert of crowds concept incorrectly:
    # avoid_map uses invert=True on "crowds" which flips human_activity positive to negative — good.

    return PreferenceVector(**{k: prefs.get(k, 0.0) for k in PreferenceVector.model_fields})


def interpret_rules(prompt: str) -> MissionIntent:
    """Offline bootstrap interpreter. Prefer LLM interpreter when available."""
    legacy = parse_constraints(prompt)
    goals: list[str] = []
    if "surprise" in legacy.style:
        goals.append("surprise")
    if "fearless_far" in legacy.style:
        goals.append("discovery")
    if "rivers" in legacy.prefer or "forests" in legacy.prefer:
        goals.append("discovery")
    if "viewpoints" in legacy.prefer:
        goals.append("photography")

    return MissionIntent(
        constraints=constraints_to_hard(legacy),
        preferences=legacy_constraints_to_preferences(legacy),
        goals=sorted(set(goals)),
        source="rules",
        interpreter_notes=[
            "rule_interpreter: legacy phrase→ontology bridge; freeze phrase expansion",
        ],
        raw_prompt=prompt,
    )
