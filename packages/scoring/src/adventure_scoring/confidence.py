"""Build per-claim confidence from independent evidence channels.

Pack-kind aware (issue #14): synthetic fixtures use weaker channel reliability
priors and a lower ceiling than real OSM+DEM packs. Values are still a
heuristic noisy-OR — not empirically calibrated against human labels.
"""

from __future__ import annotations

from typing import Literal

from adventure_core.schemas import Candidate, Confidence, ReasonCode

# Bump when priors / ceilings / combination change in a semantically meaningful way.
CALIBRATION_VERSION = "heuristic-v1"

REAL_CONFIDENCE_CEILING = 0.92
SYNTHETIC_CONFIDENCE_CEILING = 0.70
# Multiply per-channel strengths before noisy-OR for synthetic packs.
SYNTHETIC_CHANNEL_SCALE = 0.75

PackKind = Literal["synthetic", "real"]


def apply_calibration_hook(
    confidence: Confidence,
    *,
    pack_kind: PackKind,
) -> Confidence:
    """Reserved hook for post-hoc calibration against evaluation labels (#9).

    Identity today — empirical fit is deferred until labeled regional packs exist.
    Call sites should still route through this so calibration can land without
    rewriting scorers.
    """
    _ = pack_kind
    return confidence


def infer_feature_synthetic(candidate: Candidate) -> bool:
    """Heuristic pack-agnostic synthetic detection from candidate evidence."""
    source = str(candidate.evidence.get("source") or "")
    generator = str(candidate.evidence.get("generator") or "")
    provenance = candidate.evidence.get("provenance") or {}
    prov_sources = provenance.get("sources") if isinstance(provenance, dict) else None
    return (
        generator == "synthetic_fixture"
        or "synthetic" in source
        or (isinstance(prov_sources, list) and "synthetic" in prov_sources)
        or source in {"", "fixture_layers"}
    )


def resolve_pack_kind(
    candidate: Candidate,
    *,
    pack_synthetic: bool | None = None,
) -> PackKind:
    """Prefer explicit pack-manifest kind; fall back to feature evidence."""
    if pack_synthetic is True:
        return "synthetic"
    if pack_synthetic is False:
        return "real"
    return "synthetic" if infer_feature_synthetic(candidate) else "real"


def build_confidence(
    candidate: Candidate,
    *,
    pack_synthetic: bool | None = None,
) -> Confidence:
    """Combine evidence channels without pretending certainty.

    Uses a noisy-OR style combination of channel strengths, then caps when
    channels conflict (e.g. high remoteness but also high restriction).

    ``pack_synthetic`` should come from ``PackManifest.synthetic`` when known.
    Synthetic packs cannot reach the same confidence ceiling as real packs.
    """
    pack_kind = resolve_pack_kind(candidate, pack_synthetic=pack_synthetic)
    channel_scale = SYNTHETIC_CHANNEL_SCALE if pack_kind == "synthetic" else 1.0
    ceiling = SYNTHETIC_CONFIDENCE_CEILING if pack_kind == "synthetic" else REAL_CONFIDENCE_CEILING

    f = candidate.features
    channels: list[tuple[str, str, float]] = []

    if f.dist_settlement_km is not None and f.dist_settlement_km >= 15:
        channels.append(
            (
                "isolation_from_settlement",
                f"{f.dist_settlement_km:.1f} km from nearest settlement",
                min(0.85, 0.4 + f.remoteness * 0.45) * channel_scale,
            )
        )
    if f.water >= 0.6:
        if f.dist_water_km is None:
            water_detail = f"water interest {f.water:.2f} (distance unknown)"
        else:
            water_detail = f"water interest {f.water:.2f} (dist {f.dist_water_km:.1f} km)"
        channels.append(
            (
                "water_signal",
                water_detail,
                (0.35 + f.water * 0.4) * channel_scale,
            )
        )
    if f.terrain_drama >= 0.45:
        channels.append(
            (
                "terrain_relief",
                f"local relief ~{f.relief_m:.0f} m",
                (0.3 + f.terrain_drama * 0.4) * channel_scale,
            )
        )
    if f.access_fit >= 0.4:
        if f.dist_road_km is None:
            road_detail = "road distance unknown (layer missing)"
        else:
            road_detail = f"{f.dist_road_km:.1f} km from road network node"
        channels.append(
            (
                "road_access",
                road_detail,
                (0.25 + f.access_fit * 0.35) * channel_scale,
            )
        )
    if f.novelty >= 0.55:
        channels.append(
            (
                "low_human_footprint",
                f"novelty proxy {f.novelty:.2f}",
                (0.25 + f.novelty * 0.3) * channel_scale,
            )
        )

    # Noisy-OR of channel confidences
    fail = 1.0
    for _, _, c in channels:
        fail *= 1.0 - min(0.95, c)
    value = 1.0 - fail

    uncertainties: list[str] = []
    if not channels:
        value = 0.25 * channel_scale
        uncertainties.append("few_independent_evidence_channels")
    if f.risk >= 0.55:
        value *= 0.85
        uncertainties.append("elevated_hazard_flags")
    if f.restriction >= 0.5:
        value *= 0.8
        uncertainties.append("protected_or_restricted_area")
    if f.access_fit < 0.35:
        uncertainties.append("access_may_exceed_vehicle_or_time_budget")

    layer_flags = candidate.evidence.get("layer_flags") or {}
    if isinstance(layer_flags, dict):
        if layer_flags.get("settlements_layer_empty"):
            uncertainties.append("settlements_layer_missing")
        if layer_flags.get("roads_layer_empty"):
            uncertainties.append("roads_layer_missing")
        if layer_flags.get("water_layer_empty"):
            uncertainties.append("water_layer_missing")

    if pack_kind == "synthetic":
        uncertainties.append("fixture_or_sensor_resolution_limits")
        uncertainties.append("synthetic_pack_confidence_ceiling")
    else:
        uncertainties.append("sensor_and_map_resolution_limits")
    uncertainties.append("confidence_not_empirically_calibrated")

    # Never claim certainty; synthetic packs get a stricter ceiling
    value = min(ceiling, max(0.05, value))

    reasons = [ReasonCode(code=code, detail=detail) for code, detail, _ in channels]
    if not reasons:
        reasons = [
            ReasonCode(
                code="weak_evidence",
                detail="candidate lacks strong multi-channel support",
            )
        ]

    conf = Confidence(value=round(value, 3), reasons=reasons, uncertainties=uncertainties)
    return apply_calibration_hook(conf, pack_kind=pack_kind)
