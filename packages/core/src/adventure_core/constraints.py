"""Mission constraint parsing and coverage reporting."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from adventure_core.geo import Point, haversine_km

# Rough city gazetteer for origin → travel estimates (lon, lat)
CITY_COORDS: dict[str, tuple[float, float]] = {
    "lahore": (74.3587, 31.5204),
    "islamabad": (73.0479, 33.6844),
    "rawalpindi": (73.0169, 33.5651),
    "karachi": (67.0011, 24.8607),
    "peshawar": (71.5249, 34.0151),
    "multan": (71.5249, 30.1575),
    "skardu": (75.5550, 35.2971),
    "gilgit": (74.3089, 35.9208),
    "hunza": (74.65, 36.3167),
}

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

VEHICLE_ALIASES: list[tuple[str, str, str]] = [
    # phrase, normalized name, class
    ("suzuki swift", "suzuki swift", "hatchback"),
    ("honda city", "honda city", "sedan"),
    ("toyota corolla", "toyota corolla", "sedan"),
    ("hatchback", "hatchback", "hatchback"),
    ("sedan", "sedan", "sedan"),
    ("4x4", "4x4", "suv_4x4"),
    ("suv", "suv", "suv"),
    ("swift", "swift", "hatchback"),
]

ScoringStatus = Literal["used", "partial", "ignored", "not_parsed"]


class ConstraintFieldStatus(BaseModel):
    field: str
    parsed: bool
    value: Any = None
    scoring: ScoringStatus
    reason: str


class ConstraintCoverage(BaseModel):
    """Parsed → Used → Ignored report for every mission run."""

    fields: list[ConstraintFieldStatus] = Field(default_factory=list)

    @property
    def used_count(self) -> int:
        return sum(1 for f in self.fields if f.scoring in {"used", "partial"})

    @property
    def ignored_count(self) -> int:
        return sum(1 for f in self.fields if f.scoring == "ignored")


class MissionConstraints(BaseModel):
    """Structured intent extracted from a natural-language mission prompt."""

    days: float | None = None
    vehicle: str | None = None
    vehicle_class: str | None = None
    party_size: int | None = None
    budget_per_person: float | None = None
    currency: str | None = None
    origin: str | None = None
    origin_lon: float | None = None
    origin_lat: float | None = None
    prefer: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    departure: str | None = None
    return_by: str | None = None
    style: list[str] = Field(default_factory=list)

    def origin_point(self) -> Point | None:
        if self.origin_lon is None or self.origin_lat is None:
            return None
        return Point(lon=self.origin_lon, lat=self.origin_lat)


def _detect_vehicle(text: str) -> tuple[str | None, str | None]:
    for phrase, name, vclass in VEHICLE_ALIASES:
        if phrase in text:
            return name, vclass
    return None, None


def _detect_origin(text: str) -> tuple[str | None, float | None, float | None]:
    # "in Lahore", "from Lahore", "we're in Lahore"
    m = re.search(
        r"\b(?:in|from|near)\s+(" + "|".join(CITY_COORDS) + r")\b",
        text,
    )
    if m:
        city = m.group(1)
        lon, lat = CITY_COORDS[city]
        return city.title(), lon, lat
    for city, (lon, lat) in CITY_COORDS.items():
        if re.search(rf"\b{city}\b", text):
            return city.title(), lon, lat
    return None, None, None


def _weekend_days(text: str) -> float | None:
    """Friday evening → Sunday night ≈ 2.5 usable days."""
    leave_fri = bool(re.search(r"friday", text))
    back_sun = bool(re.search(r"sunday", text))
    if leave_fri and back_sun:
        if re.search(r"after work|evening", text):
            return 2.5
        return 3.0
    return None


def parse_constraints(prompt: str) -> MissionConstraints:
    """Extract structured mission constraints from natural language."""
    p = prompt.lower()
    # Normalize glued words from typos like "needto"
    p = re.sub(r"needto", "need to", p)

    days = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*days?", p)
    if m:
        days = float(m.group(1))
    else:
        m = re.search(r"\b(" + "|".join(WORD_NUMBERS) + r")\s*days?\b", p)
        if m:
            days = float(WORD_NUMBERS[m.group(1)])
    if days is None:
        days = _weekend_days(p)

    vehicle, vehicle_class = _detect_vehicle(p)

    party = None
    m = re.search(r"(\d+)\s*friends?", p)
    if m:
        party = int(m.group(1)) + 1
    else:
        m = re.search(r"\b(" + "|".join(WORD_NUMBERS) + r")\s*friends?\b", p)
        if m:
            party = WORD_NUMBERS[m.group(1)] + 1
        elif re.search(r"\bfriends\b", p) or re.search(r"\bmy friends and i\b", p):
            party = 4  # unspecified group size heuristic
        else:
            m = re.search(r"party\s*of\s*(\d+)", p)
            if m:
                party = int(m.group(1))

    budget = None
    currency = None
    m = re.search(r"(pkr|usd|eur)\s*([\d,]+)", p)
    if m:
        currency = m.group(1).upper()
        budget = float(m.group(2).replace(",", ""))
    else:
        m = re.search(r"([\d,]+)\s*(pkr|usd|eur)", p)
        if m:
            budget = float(m.group(1).replace(",", ""))
            currency = m.group(2).upper()
        else:
            m = re.search(r"(?:spend|budget|around)\s*(?:around\s*)?(pkr|usd|eur)?\s*([\d,]+)", p)
            if m and m.group(2):
                budget = float(m.group(2).replace(",", ""))
                currency = (m.group(1) or "PKR").upper()

    origin, origin_lon, origin_lat = _detect_origin(p)

    prefer: list[str] = []
    if re.search(r"\b(rivers?|riverine)\b", p) or re.search(r"love rivers?", p):
        prefer.append("rivers")
    if re.search(r"\b(forests?|woodland|trees)\b", p):
        prefer.append("forests")
    if re.search(r"\b(lakes?|alpine lake)\b", p):
        prefer.append("lakes")
    if re.search(r"\b(remote|isolation|unexplored)\b", p):
        prefer.append("remote")
    if re.search(r"\b(viewpoint|scenic|sunrise|photography)\b", p):
        prefer.append("viewpoints")

    avoid: list[str] = []
    if (
        re.search(r"(don'?t want|avoid|no).{0,24}(dangerous|risky|unsafe).{0,12}roads?", p)
        or re.search(r"dangerous roads?", p)
        and re.search(r"(don'?t|avoid|hate|no)\b", p)
    ):
        avoid.append("dangerous_roads")
    if (
        re.search(r"(hate|avoid|no).{0,16}crowds?", p)
        or re.search(r"\bcrowds?\b", p)
        and re.search(r"hate", p)
    ):
        avoid.append("crowds")

    departure = None
    if re.search(r"friday.{0,20}(after work|evening)", p) or re.search(
        r"(leave|depart).{0,20}friday", p
    ):
        departure = "friday_evening"
    elif re.search(r"\bfriday\b", p):
        departure = "friday"

    return_by = None
    if re.search(r"sunday.{0,12}night", p) or re.search(r"back by sunday", p):
        return_by = "sunday_night"
    elif re.search(r"\bsunday\b", p):
        return_by = "sunday"

    style: list[str] = []
    if re.search(r"\bsurprise\b", p):
        style.append("surprise")
    if re.search(r"fearless\s*&\s*far|fearless and far", p):
        style.append("fearless_far")

    return MissionConstraints(
        days=days,
        vehicle=vehicle,
        vehicle_class=vehicle_class,
        party_size=party,
        budget_per_person=budget,
        currency=currency,
        origin=origin,
        origin_lon=origin_lon,
        origin_lat=origin_lat,
        prefer=sorted(set(prefer)),
        avoid=sorted(set(avoid)),
        departure=departure,
        return_by=return_by,
        style=style,
    )


def estimate_one_way_hours(origin: Point, dest: Point) -> float:
    """Rough road-hours estimate (not a real router)."""
    km = haversine_km(origin, dest)
    # Mountain / mixed highway heuristic ~45 km/h effective
    return km / 45.0


def build_constraint_coverage(
    constraints: MissionConstraints,
    *,
    scoring_impacts: dict[str, tuple[ScoringStatus, str]],
) -> ConstraintCoverage:
    """Merge parsed values with per-field scoring impact declarations."""

    def status(
        field: str,
        parsed: bool,
        value: Any,
        default_ignored_reason: str = "not wired into scorer",
    ) -> ConstraintFieldStatus:
        if not parsed:
            return ConstraintFieldStatus(
                field=field,
                parsed=False,
                value=None,
                scoring="not_parsed",
                reason="not found in prompt",
            )
        impact = scoring_impacts.get(field)
        if impact:
            return ConstraintFieldStatus(
                field=field,
                parsed=True,
                value=value,
                scoring=impact[0],
                reason=impact[1],
            )
        return ConstraintFieldStatus(
            field=field,
            parsed=True,
            value=value,
            scoring="ignored",
            reason=default_ignored_reason,
        )

    fields = [
        status("vehicle", constraints.vehicle is not None, constraints.vehicle),
        status(
            "vehicle_class",
            constraints.vehicle_class is not None,
            constraints.vehicle_class,
        ),
        status("days", constraints.days is not None, constraints.days),
        status("party_size", constraints.party_size is not None, constraints.party_size),
        status(
            "budget",
            constraints.budget_per_person is not None,
            {
                "amount": constraints.budget_per_person,
                "currency": constraints.currency,
            }
            if constraints.budget_per_person is not None
            else None,
        ),
        status("origin", constraints.origin is not None, constraints.origin),
        status("prefer", bool(constraints.prefer), constraints.prefer),
        status("avoid", bool(constraints.avoid), constraints.avoid),
        status("departure", constraints.departure is not None, constraints.departure),
        status("return_by", constraints.return_by is not None, constraints.return_by),
        status("style", bool(constraints.style), constraints.style),
    ]
    return ConstraintCoverage(fields=fields)
