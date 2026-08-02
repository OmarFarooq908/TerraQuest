"""Deterministic ranking explanations — why a place scored (not how sure).

Derived from score breakdowns + evidence. Never invents candidates or alters
scores. See RFC-0009 / issue #27.
"""

from __future__ import annotations

from typing import Any

from adventure_core.schemas import ReasonCode

_SKIP_PREF_KEYS = frozenset(
    {"_alignment", "_pref_strength", "_factor", "goal_factor", "origin_one_way_hours"}
)
_MODE_KEYS = (
    "remoteness",
    "terrain_drama",
    "water",
    "viewpoint",
    "novelty",
    "access_fit",
    "camping",
)


def _sort_key(item: tuple[float, ReasonCode]) -> tuple[float, str]:
    return (-item[0], item[1].code)


def build_ranking_explanations(
    *,
    feature_breakdown: dict[str, float],
    preference_adjustments: dict[str, float],
    evidence: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    max_reasons: int = 6,
) -> list[ReasonCode]:
    """Build ≤``max_reasons`` human-readable ranking reasons (deterministic).

    Selection is **category-aware** so large mode priors cannot entirely hide
    preference / constraint drivers (CLI trust).
    """
    prefs: list[tuple[float, ReasonCode]] = []
    modes: list[tuple[float, ReasonCode]] = []
    constraints: list[tuple[float, ReasonCode]] = []
    goals: list[tuple[float, ReasonCode]] = []
    risks: list[tuple[float, ReasonCode]] = []
    info: list[ReasonCode] = []

    for key in _MODE_KEYS:
        contrib = float(feature_breakdown.get(key, 0.0) or 0.0)
        if abs(contrib) < 0.03:
            continue
        modes.append(
            (
                abs(contrib),
                ReasonCode(
                    code=f"mode.{key}",
                    detail=f"mode prior favors {key.replace('_', ' ')} ({contrib:+.2f})",
                ),
            )
        )

    for key, raw in preference_adjustments.items():
        if key in _SKIP_PREF_KEYS or key.startswith("_"):
            continue
        if key in {"origin_travel", "budget_access_nudge"}:
            continue
        contrib = float(raw)
        if abs(contrib) < 0.02:
            continue
        if contrib >= 0:
            detail = f"matches {key} preference ({contrib:+.2f})"
        else:
            detail = f"conflicts with {key} preference ({contrib:+.2f})"
        prefs.append((abs(contrib), ReasonCode(code=f"pref.{key}", detail=detail)))

    origin = preference_adjustments.get("origin_travel")
    if origin is not None and float(origin) < -0.02:
        hours = preference_adjustments.get("origin_one_way_hours")
        hours_s = f", ~{float(hours):.1f}h one-way" if hours is not None else ""
        constraints.append(
            (
                abs(float(origin)),
                ReasonCode(
                    code="constraint.origin_travel",
                    detail=f"travel-time penalty ({float(origin):+.2f}{hours_s})",
                ),
            )
        )

    budget = preference_adjustments.get("budget_access_nudge")
    if budget is not None and abs(float(budget)) >= 0.02:
        constraints.append(
            (
                abs(float(budget)),
                ReasonCode(
                    code="constraint.budget_access",
                    detail=f"budget↔access nudge ({float(budget):+.2f})",
                ),
            )
        )

    g = preference_adjustments.get("goal_factor")
    if g is not None and float(g) >= 1.02:
        goals.append(
            (
                float(g) - 1.0,
                ReasonCode(
                    code="goal.boost",
                    detail=f"mission goals boosted score (×{float(g):.2f})",
                ),
            )
        )

    risk_f = feature_breakdown.get("risk_factor")
    if risk_f is not None and float(risk_f) <= 0.85:
        risks.append(
            (
                1.0 - float(risk_f),
                ReasonCode(
                    code="mode.risk",
                    detail=f"risk penalty applied (×{float(risk_f):.2f})",
                ),
            )
        )

    ev = evidence or {}
    gen = ev.get("generator")
    if isinstance(gen, str) and gen.strip():
        info.append(
            ReasonCode(
                code="evidence.generator",
                detail=f"surfaced by generator `{gen.strip()}`",
            )
        )
    oids = ev.get("ontology_ids")
    if isinstance(oids, list) and oids:
        canon = [str(x) for x in oids if isinstance(x, str) and x.strip()][:3]
        if canon:
            info.append(
                ReasonCode(
                    code="evidence.ontology",
                    detail="ontology: " + ", ".join(canon),
                )
            )
    elif tags:
        tag_s = ", ".join(t for t in tags[:4] if t not in {"fearless", "far", "control"})
        if tag_s:
            info.append(ReasonCode(code="evidence.tags", detail=f"tags: {tag_s}"))

    for bucket in (prefs, modes, constraints, goals, risks):
        bucket.sort(key=_sort_key)

    out: list[ReasonCode] = []
    seen: set[str] = set()

    # Prefer trust-critical categories over large mode priors.
    # Reserve one slot for catalog evidence context when present.
    reserve_info = 1 if info else 0
    hard_cap = max(0, max_reasons - reserve_info)

    def _take(bucket: list[tuple[float, ReasonCode]], n: int) -> None:
        for _, rc in bucket:
            if len(out) >= hard_cap or n <= 0:
                return
            if rc.code in seen:
                continue
            out.append(rc)
            seen.add(rc.code)
            n -= 1

    _take(constraints, 2)
    _take(prefs, 3)
    _take(goals, 1)
    _take(risks, 1)
    _take(modes, 3)

    for rc in info:
        if len(out) >= max_reasons:
            break
        if rc.code not in seen:
            out.append(rc)
            seen.add(rc.code)

    # Pad with remaining strongest drivers if still short
    remainder = sorted(prefs + modes + constraints + goals + risks, key=_sort_key)
    for _, rc in remainder:
        if len(out) >= max_reasons:
            break
        if rc.code not in seen:
            out.append(rc)
            seen.add(rc.code)

    return out
