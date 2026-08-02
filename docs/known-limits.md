# Known limits

Documented so contributors do not “fix” them with architecture-breaking PRs.

| Limit | Status |
|-------|--------|
| Travel time | Haversine / 45 km/h heuristic — not a road router |
| `party_size` | Parsed; camping capacity not scored |
| Confidence | Heuristic noisy-OR; not empirically calibrated |
| Overpass ingest | Degraded (no road_lines); opt-in only |
| LLM intent | Polarity repair mitigates sign flips; `--interpreter rules` for CI |
| Sentinel-2 | Not in v1 packs |
| Mission-time densify | Schema hooks only (Phase C later) |
| Missing GIS layers | Empty settlements/roads/water → `dist_*_km=null`, neutral remoteness 0.5, evidence `layer_flags` — never `-1` / `999` sentinels |

## Feature ranges

Unit-interval features on `CandidateFeatures` (`remoteness`, `crowd`, …) are always in **[0, 1]** (Pydantic-enforced). Distance fields are non-negative kilometers or **`null`** when the supporting pack layer is empty.
Propose changes via an RFC under the repository `RFC/` directory (see `RFC/README.md`).
