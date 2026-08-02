"""Prompt polarity cues → expected preference signs (anti-inversion).

Ontology RFC will eventually own concept IDs; until then these cues are the
shared lexicon for detecting preference inversions across interpreters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from adventure_core.intent import PREFERENCE_DIMENSIONS, MissionIntent, PreferenceVector

InversionKind = Literal["inverted", "missing"]


@dataclass(frozen=True)
class PolarityCue:
    """A high-confidence phrase family that implies preference polarity."""

    id: str
    pattern: re.Pattern[str]
    # dimension → expected sign (+1 want more, -1 want less)
    expectations: dict[str, Literal[-1, 1]]
    strength: float = 0.75


@dataclass(frozen=True)
class PolarityFinding:
    cue_id: str
    dimension: str
    kind: InversionKind
    expected_sign: Literal[-1, 1]
    observed: float


# Keep patterns conservative — only clear polarity language.
POLARITY_CUES: tuple[PolarityCue, ...] = (
    PolarityCue(
        id="hate_crowds",
        pattern=re.compile(
            r"(?i)\b(hate|avoid|no|without)\b.{0,20}\bcrowds?\b"
            r"|\bcrowds?\b.{0,12}\b(hate|avoid)\b"
            r"|\b(quiet|peaceful)\b(?!.{0,20}\b(party|festival)\b)"
        ),
        expectations={"human_activity": -1, "solitude": 1},
    ),
    PolarityCue(
        id="seek_solitude",
        pattern=re.compile(r"(?i)\b(solitude|secluded|away from (people|crowds?))\b"),
        expectations={"solitude": 1, "human_activity": -1},
    ),
    PolarityCue(
        id="love_crowds",
        pattern=re.compile(
            r"(?i)\b(love|want|enjoy)\b.{0,16}\bcrowds?\b"
            r"|\b(lively|bustling|nightlife|busy (town|city|bazaar))\b"
        ),
        expectations={"human_activity": 1},
    ),
    PolarityCue(
        id="avoid_danger",
        pattern=re.compile(
            r"(?i)(don'?t want|avoid|no|hate).{0,24}(dangerous|risky|unsafe).{0,12}roads?"
            r"|\b(safe roads?|easy access)\b"
        ),
        expectations={"danger": -1, "accessibility": 1},
    ),
    PolarityCue(
        id="seek_challenge",
        pattern=re.compile(
            r"(?i)(?<!don't\s)(?<!dont\s)(?<!do not\s)(?<!avoid\s)(?<!no\s)"
            r"\b(seek|want|love)\b.{0,20}\b(challenge|technical (tracks?|terrain))\b"
            r"|\b(love|seek)\b.{0,12}\bdangerous roads?\b"
        ),
        expectations={"danger": 1},
    ),
    PolarityCue(
        id="love_water",
        pattern=re.compile(r"(?i)\b(love|want|prefer)\b.{0,16}\b(rivers?|lakes?|waterfalls?)\b"),
        expectations={"water": 1},
    ),
    PolarityCue(
        id="love_forest",
        pattern=re.compile(r"(?i)\b(love|want|prefer)\b.{0,16}\b(forests?|woodland|trees)\b"),
        expectations={"forest": 1},
    ),
    PolarityCue(
        id="seek_remote",
        pattern=re.compile(
            r"(?i)\b(remote|untouched|unexplored|far from (town|people|settlements?))\b"
            r"|\bfearless\s*&\s*far\b|\bfearless and far\b"
        ),
        expectations={"remoteness": 1, "novelty": 1},
    ),
    PolarityCue(
        id="hate_hiking",
        pattern=re.compile(r"(?i)\b(hate|avoid|no)\b.{0,16}\b(hiking|trekking|long walks?)\b"),
        expectations={"hiking": -1, "accessibility": 1},
    ),
    PolarityCue(
        id="want_camping",
        pattern=re.compile(r"(?i)\b(want|love|prefer)\b.{0,16}\bcamp(ing)?\b"),
        expectations={"camping": 1},
    ),
)


def detect_preference_inversions(
    prompt: str,
    preferences: PreferenceVector,
    *,
    active_eps: float = 0.05,
) -> list[PolarityFinding]:
    """Compare prompt polarity cues to preference signs."""
    prefs = preferences.as_dict()
    findings: list[PolarityFinding] = []
    seen: set[tuple[str, str, str]] = set()

    for cue in POLARITY_CUES:
        if not cue.pattern.search(prompt):
            continue
        for dim, sign in cue.expectations.items():
            if dim not in PREFERENCE_DIMENSIONS:
                continue
            observed = float(prefs.get(dim, 0.0))
            if abs(observed) < active_eps:
                kind: InversionKind = "missing"
            elif observed * float(sign) < 0:
                kind = "inverted"
            else:
                continue
            key = (cue.id, dim, kind)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                PolarityFinding(
                    cue_id=cue.id,
                    dimension=dim,
                    kind=kind,
                    expected_sign=sign,
                    observed=observed,
                )
            )
    return findings


def repair_preference_inversions(
    intent: MissionIntent,
    *,
    prompt: str | None = None,
    min_abs: float = 0.55,
) -> tuple[MissionIntent, list[PolarityFinding]]:
    """Repair inverted/missing preferences implied by the prompt.

    Returns (possibly updated intent, findings that were considered).
    Always records interpreter_notes when repairs are applied.
    """
    text = prompt if prompt is not None else (intent.raw_prompt or "")
    if not text.strip():
        return intent, []

    findings = detect_preference_inversions(text, intent.preferences)
    if not findings:
        return intent, findings

    prefs = intent.preferences.model_copy()
    notes = list(intent.interpreter_notes)
    repaired = 0
    for finding in findings:
        cue = next(c for c in POLARITY_CUES if c.id == finding.cue_id)
        target = float(finding.expected_sign) * max(min_abs, cue.strength)
        current = float(getattr(prefs, finding.dimension))
        if finding.kind == "inverted" or (finding.kind == "missing" and abs(current) < 0.05):
            setattr(prefs, finding.dimension, max(-1.0, min(1.0, target)))
            notes.append(
                f"polarity_repair:{finding.kind}:{finding.cue_id}:{finding.dimension}"
                f":{current:+.2f}->{target:+.2f}"
            )
            repaired += 1

    if repaired == 0:
        return intent, findings

    return (
        intent.model_copy(update={"preferences": prefs, "interpreter_notes": notes}),
        findings,
    )
