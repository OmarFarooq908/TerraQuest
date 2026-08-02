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


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pref_detail(
    dim: str,
    contrib: float,
    *,
    weight: float | None,
    feature: float | None,
) -> str:
    """Describe preference contribution without match/conflict sign bugs.

    ``contrib = weight * feature``. Negative weights (avoid-X) never yield
    positive contrib when feature ≥ 0, so "conflicts" on sign(contrib) is wrong.
    """
    if weight is not None and weight <= -0.05:
        if feature is not None and feature <= 0.35:
            return f"honors avoid-{dim} preference ({dim}={feature:.2f})"
        if feature is not None:
            return f"higher {dim} than preferred ({dim}={feature:.2f}, contrib {contrib:+.2f})"
        return f"avoid-{dim} preference contribution ({contrib:+.2f})"
    if weight is not None and weight >= 0.05:
        if contrib >= 0.02:
            return f"matches {dim} preference ({contrib:+.2f})"
        return f"weak {dim} for preference ({contrib:+.2f})"
    return f"{dim} preference contribution ({contrib:+.2f})"


def _pref_sort_magnitude(
    contrib: float,
    *,
    weight: float | None,
    feature: float | None,
) -> float:
    """Importance for selection — honor avoid-prefs when the feature is low."""
    if weight is not None and weight <= -0.05 and feature is not None:
        # Strong avoid + low feature is a success story; surface it.
        return max(abs(contrib), abs(weight) * (1.0 - feature))
    return abs(contrib)


def build_ranking_explanations(
    *,
    feature_breakdown: dict[str, float],
    preference_adjustments: dict[str, float],
    evidence: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    preference_weights: dict[str, float] | None = None,
    dimensions: dict[str, float] | None = None,
    max_reasons: int = 6,
) -> list[ReasonCode]:
    """Build ≤``max_reasons`` human-readable ranking reasons (deterministic).

    Selection is **category-aware** so large mode priors cannot entirely hide
    preference / constraint drivers (CLI trust).

    Pass ``preference_weights`` + ``dimensions`` when available so avoid-*
    preferences are explained correctly (not as false "conflicts").
    """
    if max_reasons <= 0:
        return []

    prefs: list[tuple[float, ReasonCode]] = []
    modes: list[tuple[float, ReasonCode]] = []
    constraints: list[tuple[float, ReasonCode]] = []
    goals: list[tuple[float, ReasonCode]] = []
    risks: list[tuple[float, ReasonCode]] = []
    info: list[ReasonCode] = []

    weights = preference_weights or {}
    dims = dimensions or {}
    # dimensions often live on evidence when called from rank_missions
    ev = evidence or {}
    if not dims and isinstance(ev.get("dimensions"), dict):
        dims = {str(k): float(v) for k, v in ev["dimensions"].items() if _as_float(v) is not None}

    for key in _MODE_KEYS:
        contrib = _as_float(feature_breakdown.get(key, 0.0)) or 0.0
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
        contrib = _as_float(raw)
        if contrib is None or abs(contrib) < 0.02:
            # Still surface successful avoid-prefs with tiny |contrib|
            w = _as_float(weights.get(key))
            x = _as_float(dims.get(key))
            if not (w is not None and w <= -0.05 and x is not None and x <= 0.35):
                continue
            contrib = float(contrib or (w * x))
        w = _as_float(weights.get(key))
        x = _as_float(dims.get(key))
        mag = _pref_sort_magnitude(contrib, weight=w, feature=x)
        if mag < 0.02:
            continue
        prefs.append(
            (
                mag,
                ReasonCode(
                    code=f"pref.{key}",
                    detail=_pref_detail(key, contrib, weight=w, feature=x),
                ),
            )
        )

    origin = _as_float(preference_adjustments.get("origin_travel"))
    if origin is not None and origin < -0.02:
        hours = _as_float(preference_adjustments.get("origin_one_way_hours"))
        hours_s = f", ~{hours:.1f}h one-way" if hours is not None else ""
        constraints.append(
            (
                abs(origin),
                ReasonCode(
                    code="constraint.origin_travel",
                    detail=f"travel-time penalty ({origin:+.2f}{hours_s})",
                ),
            )
        )

    budget = _as_float(preference_adjustments.get("budget_access_nudge"))
    if budget is not None and abs(budget) >= 0.02:
        constraints.append(
            (
                abs(budget),
                ReasonCode(
                    code="constraint.budget_access",
                    detail=f"budget↔access nudge ({budget:+.2f})",
                ),
            )
        )

    g = _as_float(preference_adjustments.get("goal_factor"))
    if g is not None and g >= 1.02:
        goals.append(
            (
                g - 1.0,
                ReasonCode(
                    code="goal.boost",
                    detail=f"mission goals boosted score (×{g:.2f})",
                ),
            )
        )

    risk_f = _as_float(feature_breakdown.get("risk_factor"))
    if risk_f is not None and risk_f <= 0.85:
        risks.append(
            (
                1.0 - risk_f,
                ReasonCode(
                    code="mode.risk",
                    detail=f"risk penalty applied (×{risk_f:.2f})",
                ),
            )
        )

    restriction_f = _as_float(feature_breakdown.get("restriction_factor"))
    if restriction_f is not None and restriction_f <= 0.85:
        risks.append(
            (
                1.0 - restriction_f,
                ReasonCode(
                    code="mode.restriction",
                    detail=f"restriction penalty applied (×{restriction_f:.2f})",
                ),
            )
        )

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
    if not any(r.code == "evidence.ontology" for r in info) and tags:
        tag_s = ", ".join(t for t in tags[:4] if t not in {"fearless", "far", "control"})
        if tag_s:
            info.append(ReasonCode(code="evidence.tags", detail=f"tags: {tag_s}"))

    for bucket in (prefs, modes, constraints, goals, risks):
        bucket.sort(key=_sort_key)

    out: list[ReasonCode] = []
    seen: set[str] = set()

    # Reserve slots for catalog evidence (generator + ontology/tags).
    reserve_info = min(len(info), 2)
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

    remainder = sorted(prefs + modes + constraints + goals + risks, key=_sort_key)
    for _, rc in remainder:
        if len(out) >= max_reasons:
            break
        if rc.code not in seen:
            out.append(rc)
            seen.add(rc.code)

    return out
