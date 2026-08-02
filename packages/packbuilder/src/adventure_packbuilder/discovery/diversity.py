"""Per-generator quota + spatial diversity selection."""

from __future__ import annotations

from collections.abc import Callable

from adventure_core.catalog import CatalogCandidate
from adventure_core.geo import Point, haversine_km


def select_diverse(
    candidates: list[CatalogCandidate],
    *,
    quota: int,
    min_spacing_km: float,
    score_fn: Callable[[CatalogCandidate], float] | None = None,
) -> list[CatalogCandidate]:
    """Greedy select by descending score with minimum spacing."""
    if quota <= 0 or not candidates:
        return []
    scored = list(candidates)
    if score_fn is None:

        def score_fn(c: CatalogCandidate) -> float:
            return float(c.evidence.get("discovery_score", 0.0))

    scored.sort(key=score_fn, reverse=True)
    chosen: list[CatalogCandidate] = []
    for cand in scored:
        pt = Point(cand.lon, cand.lat)
        if any(haversine_km(pt, Point(c.lon, c.lat)) < min_spacing_km for c in chosen):
            continue
        chosen.append(cand)
        if len(chosen) >= quota:
            break
    return chosen


def merge_catalog_diverse(
    groups: list[list[CatalogCandidate]],
    *,
    global_min_spacing_km: float,
) -> list[CatalogCandidate]:
    """Merge generator outputs; soft global spacing across generators."""
    merged: list[CatalogCandidate] = []
    # Prefer higher discovery_score when resolving near-duplicates across gens
    flat = [c for g in groups for c in g]
    flat.sort(key=lambda c: float(c.evidence.get("discovery_score", 0.0)), reverse=True)
    for cand in flat:
        pt = Point(cand.lon, cand.lat)
        conflict = None
        for i, existing in enumerate(merged):
            if haversine_km(pt, Point(existing.lon, existing.lat)) < global_min_spacing_km:
                conflict = i
                break
        if conflict is None:
            merged.append(cand)
            continue
        # Keep the higher-scoring / prefer non-synthetic generator already sorted
        # Skip duplicate location
        continue
    return merged
