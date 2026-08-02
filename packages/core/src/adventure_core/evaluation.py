"""Evaluation place-label schema and discovery-quality metrics (RFC-0002 / RFC-0005)."""

from __future__ import annotations

import json
import math
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from adventure_core.geo import Point, haversine_km

PLACE_LABEL_SCHEMA_VERSION = "0.1.0"

# North Star pin (RFC-0005) — must match configs/north_star.yaml.
# Harness / metric defaults must use these (or load_north_star_config()), not literals.
NORTH_STAR_PRIMARY_METRIC = "recall_at_k"
NORTH_STAR_PRIMARY_LABEL_FILTER = "interesting"
NORTH_STAR_K = 5
NORTH_STAR_GUARDRAIL_METRIC = "popularity_trap_at_k"
NORTH_STAR_POPULARITY_THRESHOLD = 7.0
NORTH_STAR_MATCH_RADIUS_KM = 2.0
NORTH_STAR_DEFAULT_MODE = "fearless_far"


class NorthStarConfig(BaseModel):
    """Pinned primary metric + guardrail (RFC-0005)."""

    primary_metric: str = NORTH_STAR_PRIMARY_METRIC
    primary_label_filter: str = NORTH_STAR_PRIMARY_LABEL_FILTER
    k: int = NORTH_STAR_K
    guardrail_metric: str = NORTH_STAR_GUARDRAIL_METRIC
    popularity_threshold: float = NORTH_STAR_POPULARITY_THRESHOLD
    match_radius_km: float = NORTH_STAR_MATCH_RADIUS_KM
    default_mode: str = NORTH_STAR_DEFAULT_MODE


def _pin_str(raw: dict[str, Any], key: str, default: str) -> str:
    val = raw.get(key)
    if val is None:
        return default
    text = str(val).strip()
    return text if text else default


def _pin_int(raw: dict[str, Any], key: str, default: int) -> int:
    val = raw.get(key)
    return default if val is None else int(val)


def _pin_float(raw: dict[str, Any], key: str, default: float) -> float:
    val = raw.get(key)
    return default if val is None else float(val)


def load_north_star_config() -> NorthStarConfig:
    """Load ``configs/north_star.yaml``; fall back to module constants."""
    from adventure_core.config import configs_dir, load_yaml

    path = configs_dir() / "north_star.yaml"
    if not path.is_file():
        return NorthStarConfig()
    raw = load_yaml(path)
    return NorthStarConfig(
        primary_metric=_pin_str(raw, "primary_metric", NORTH_STAR_PRIMARY_METRIC),
        primary_label_filter=_pin_str(raw, "primary_label_filter", NORTH_STAR_PRIMARY_LABEL_FILTER),
        k=_pin_int(raw, "k", NORTH_STAR_K),
        guardrail_metric=_pin_str(raw, "guardrail_metric", NORTH_STAR_GUARDRAIL_METRIC),
        popularity_threshold=_pin_float(
            raw, "popularity_threshold", NORTH_STAR_POPULARITY_THRESHOLD
        ),
        match_radius_km=_pin_float(raw, "match_radius_km", NORTH_STAR_MATCH_RADIUS_KM),
        default_mode=_pin_str(raw, "default_mode", NORTH_STAR_DEFAULT_MODE),
    )


def north_star_constants_match_config(cfg: NorthStarConfig | None = None) -> bool:
    """True when module constants agree with ``configs/north_star.yaml``."""
    pin = cfg or load_north_star_config()
    return (
        pin.primary_metric == NORTH_STAR_PRIMARY_METRIC
        and pin.primary_label_filter == NORTH_STAR_PRIMARY_LABEL_FILTER
        and pin.k == NORTH_STAR_K
        and pin.guardrail_metric == NORTH_STAR_GUARDRAIL_METRIC
        and pin.popularity_threshold == NORTH_STAR_POPULARITY_THRESHOLD
        and pin.match_radius_km == NORTH_STAR_MATCH_RADIUS_KM
        and pin.default_mode == NORTH_STAR_DEFAULT_MODE
    )


class GeoJSONPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]  # lon, lat

    @field_validator("coordinates")
    @classmethod
    def _lon_lat(cls, v: tuple[float, float]) -> tuple[float, float]:
        lon, lat = float(v[0]), float(v[1])
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise ValueError("coordinates must be WGS84 lon/lat")
        return (lon, lat)

    def as_point(self) -> Point:
        return Point(lon=self.coordinates[0], lat=self.coordinates[1])


class PlaceLabel(BaseModel):
    """Curator or synthetic rating for a place used in discovery evaluation."""

    schema_version: str = PLACE_LABEL_SCHEMA_VERSION
    id: str
    catalog_id: str | None = None
    geometry: GeoJSONPoint
    known: bool
    interesting: bool
    human_rating: float | None = None
    google_maps_popularity: float | None = None
    tags: list[str] = Field(default_factory=list)
    ontology_ids: list[str] = Field(default_factory=list)
    notes: str | None = None
    license: str
    synthetic: bool = False

    @field_validator("human_rating", "google_maps_popularity")
    @classmethod
    def _optional_0_10(cls, v: float | None) -> float | None:
        if v is None:
            return None
        x = float(v)
        if not (0.0 <= x <= 10.0):
            raise ValueError("ratings must be in [0, 10] when set")
        return x

    @field_validator("schema_version")
    @classmethod
    def _schema(cls, v: str) -> str:
        if v != PLACE_LABEL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported place label schema_version {v!r}; "
                f"expected {PLACE_LABEL_SCHEMA_VERSION!r}"
            )
        return v


class RankedRef(BaseModel):
    """Minimal ranked mission reference for metrics (avoids scoring import cycles)."""

    candidate_id: str
    score: float
    lon: float | None = None
    lat: float | None = None


class Match(BaseModel):
    rank_index: int  # 0-based in the ranked list considered
    candidate_id: str
    label_id: str
    score: float
    interesting: bool
    human_rating: float | None = None
    google_maps_popularity: float | None = None
    match_via: Literal["catalog_id", "distance"]


class DiscoveryMetrics(BaseModel):
    k: int
    n_labels: int
    n_interesting: int
    n_ranked: int
    n_matched: int
    recall_at_k: float | None
    precision_at_k: float | None
    popularity_trap_at_k: float | None
    rating_spearman: float | None
    ndcg_at_k: float | None
    match_radius_km: float
    popularity_threshold: float


def load_place_labels(path: Path) -> list[PlaceLabel]:
    """Load labels from a JSON file or a directory of `*.json` arrays."""
    path = path.expanduser().resolve()
    files: list[Path]
    if path.is_dir():
        files = sorted(path.glob("*.json"))
    elif path.is_file():
        files = [path]
    else:
        raise FileNotFoundError(path)

    labels: list[PlaceLabel] = []
    for fp in files:
        raw = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{fp}: expected a JSON array of place labels")
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"{fp}[{i}]: expected object")
            labels.append(PlaceLabel.model_validate(item))
    return labels


def match_ranked_to_labels(
    ranked: Iterable[RankedRef],
    labels: Iterable[PlaceLabel],
    *,
    k: int,
    match_radius_km: float = NORTH_STAR_MATCH_RADIUS_KM,
) -> list[Match]:
    """Greedy match top-k ranked refs to labels (each label used at most once)."""
    label_list = list(labels)
    by_catalog = {lb.catalog_id: lb for lb in label_list if lb.catalog_id}
    used: set[str] = set()
    matches: list[Match] = []

    for idx, ref in enumerate(list(ranked)[: max(0, k)]):
        hit: PlaceLabel | None = None
        via: Literal["catalog_id", "distance"] = "catalog_id"

        if ref.candidate_id in by_catalog:
            cand = by_catalog[ref.candidate_id]
            if cand.id not in used:
                hit = cand
                via = "catalog_id"

        if hit is None and ref.lon is not None and ref.lat is not None:
            origin = Point(lon=ref.lon, lat=ref.lat)
            best: tuple[float, PlaceLabel] | None = None
            for lb in label_list:
                if lb.id in used:
                    continue
                d = haversine_km(origin, lb.geometry.as_point())
                if d <= match_radius_km and (best is None or d < best[0]):
                    best = (d, lb)
            if best is not None:
                hit = best[1]
                via = "distance"

        if hit is None:
            continue
        used.add(hit.id)
        matches.append(
            Match(
                rank_index=idx,
                candidate_id=ref.candidate_id,
                label_id=hit.id,
                score=float(ref.score),
                interesting=hit.interesting,
                human_rating=hit.human_rating,
                google_maps_popularity=hit.google_maps_popularity,
                match_via=via,
            )
        )
    return matches


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None

    # Average ranks for ties
    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    if den_x == 0.0 or den_y == 0.0:
        return None
    return num / (den_x * den_y)


def _dcg(relevances: list[float]) -> float:
    total = 0.0
    for i, rel in enumerate(relevances):
        total += (2.0**rel - 1.0) / math.log2(i + 2.0)
    return total


def ndcg_at_k(
    ranked: Iterable[RankedRef],
    labels: Iterable[PlaceLabel],
    *,
    k: int = NORTH_STAR_K,
    match_radius_km: float = NORTH_STAR_MATCH_RADIUS_KM,
    ideal_catalog_ids: Collection[str] | None = None,
) -> float | None:
    """nDCG@k using ``human_rating`` as graded relevance (RFC-0002 / issue #24).

    Unmatched ranks contribute 0. Ideal DCG uses the top-k label ratings
    (descending). When ``ideal_catalog_ids`` is set (generator ablations), the
    ideal is restricted to those catalog ids so family pools are comparable.
    Returns ``None`` when fewer than two rated labels remain in the ideal set.
    """
    label_list = list(labels)
    if ideal_catalog_ids is not None:
        allow = set(ideal_catalog_ids)
        rated_labels = [
            lb
            for lb in label_list
            if lb.human_rating is not None and lb.catalog_id is not None and lb.catalog_id in allow
        ]
    else:
        rated_labels = [lb for lb in label_list if lb.human_rating is not None]
    rated = [float(lb.human_rating) for lb in rated_labels if lb.human_rating is not None]
    if len(rated) < 2:
        return None

    matches = match_ranked_to_labels(ranked, label_list, k=k, match_radius_km=match_radius_km)
    by_rank = {m.rank_index: m for m in matches}
    gains: list[float] = []
    for i in range(max(0, k)):
        m = by_rank.get(i)
        if m is not None and m.human_rating is not None:
            gains.append(float(m.human_rating))
        else:
            gains.append(0.0)

    ideal = sorted(rated, reverse=True)[: max(0, k)]
    while len(ideal) < len(gains):
        ideal.append(0.0)
    idcg = _dcg(ideal)
    if idcg <= 0.0:
        return None
    return _dcg(gains) / idcg


def compute_discovery_metrics(
    ranked: Iterable[RankedRef],
    labels: Iterable[PlaceLabel],
    *,
    k: int = NORTH_STAR_K,
    match_radius_km: float = NORTH_STAR_MATCH_RADIUS_KM,
    popularity_threshold: float = NORTH_STAR_POPULARITY_THRESHOLD,
    ideal_catalog_ids: Collection[str] | None = None,
) -> DiscoveryMetrics:
    label_list = list(labels)
    ranked_list = list(ranked)
    interesting = [lb for lb in label_list if lb.interesting]
    matches = match_ranked_to_labels(ranked_list, label_list, k=k, match_radius_km=match_radius_km)
    matched_interesting_ids = {m.label_id for m in matches if m.interesting}
    recall = len(matched_interesting_ids) / len(interesting) if interesting else None
    precision = sum(1 for m in matches if m.interesting) / len(matches) if matches else None
    with_pop = [m for m in matches if m.google_maps_popularity is not None]
    trap = (
        sum(
            1
            for m in with_pop
            if m.google_maps_popularity is not None
            and m.google_maps_popularity >= popularity_threshold
        )
        / len(with_pop)
        if with_pop
        else None
    )
    rated = [(m.score, m.human_rating) for m in matches if m.human_rating is not None]
    spearman = _spearman([s for s, _ in rated], [float(r) for _, r in rated]) if rated else None
    ndcg = ndcg_at_k(
        ranked_list,
        label_list,
        k=k,
        match_radius_km=match_radius_km,
        ideal_catalog_ids=ideal_catalog_ids,
    )
    return DiscoveryMetrics(
        k=k,
        n_labels=len(label_list),
        n_interesting=len(interesting),
        n_ranked=len(ranked_list),
        n_matched=len(matches),
        recall_at_k=recall,
        precision_at_k=precision,
        popularity_trap_at_k=trap,
        rating_spearman=spearman,
        ndcg_at_k=ndcg,
        match_radius_km=match_radius_km,
        popularity_threshold=popularity_threshold,
    )


def metrics_as_dict(m: DiscoveryMetrics) -> dict[str, Any]:
    return m.model_dump()
