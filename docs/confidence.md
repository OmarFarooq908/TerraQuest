# Confidence model

How Adventure AI scores **claim confidence** on ranked missions — and what it
does *not* claim.

## Summary

Confidence is a **heuristic noisy-OR** over independent GIS evidence channels
(`adventure_scoring.confidence.build_confidence`). It is **not** an empirically
calibrated probability of “this place is a good adventure.”

Calibration version string (surfaced on every `MissionResult` as
`confidence_calibration=…`):

`heuristic-v1`

## Channels

When present and strong enough, these contribute:

| Channel | Trigger (approx.) |
|---------|-------------------|
| Isolation from settlement | `dist_settlement_km ≥ 15` |
| Water signal | `water ≥ 0.6` |
| Terrain relief | `terrain_drama ≥ 0.45` |
| Road access | `access_fit ≥ 0.4` |
| Low human footprint | `novelty ≥ 0.55` |

Risk / restriction dampen the combined value. Missing layers add uncertainty
codes (`*_layer_missing`) rather than inventing distances.

## Pack kind (synthetic vs real)

`PackManifest.synthetic` is passed through `rank_missions(..., pack_synthetic=…)`.

| Pack kind | Channel prior scale | Hard ceiling |
|-----------|---------------------|--------------|
| **real** (OSM+DEM) | `1.0` | `0.92` |
| **synthetic** (fixtures) | `0.75` | `0.70` |

Synthetic packs also carry uncertainty tags
`fixture_or_sensor_resolution_limits` and `synthetic_pack_confidence_ceiling`.
Real packs use `sensor_and_map_resolution_limits`.

Both kinds always include `confidence_not_empirically_calibrated`.

When `pack_synthetic` is omitted, confidence falls back to feature-level
heuristics (generator / provenance / source strings) so unit tests stay simple.

## Hook for future calibration

`apply_calibration_hook(confidence, *, pack_kind)` is an identity function today.
Once evaluation place labels exist ([issue #9](https://github.com/OmarFarooq908/TerraQuest/issues/9)),
post-hoc mapping (isotonic / Platt / reliability diagrams) can land here without
rewriting the scorer.

## What not to do

- Do not treat `confidence.value` as a survey-grade probability.
- Do not raise the synthetic ceiling to match real packs without labeled evidence.
- Do not remove pack-kind gating to “make fixtures look more confident.”
