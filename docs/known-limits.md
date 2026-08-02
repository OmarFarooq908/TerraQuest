# Known limits

Documented so contributors do not “fix” them with architecture-breaking PRs.

| Limit | Status |
|-------|--------|
| Travel time | Haversine / 45 km/h heuristic — not a road router |
| GIS features | Distance + settlement-density kernel + road-class `access_fit`; no DEM prominence / polygon edges yet — see [GIS features](gis-features.md) |
| `party_size` | Parsed; camping capacity not scored |
| Confidence | Heuristic noisy-OR with **pack-kind priors** (synthetic ceiling lower than real); not empirically calibrated — see [confidence](confidence.md) |
| Overpass ingest | Degraded (no road_lines); opt-in only |
| LLM intent | Local Ollama only by default (no cloud keys); validation + polarity repair; `--interpreter rules` for CI — see [offline inference](offline-inference.md) |
| Sentinel-2 | Not in v1 packs |
| Mission-time densify | Schema hooks only (Phase C later) |
| Missing GIS layers | Empty settlements/roads/water → `dist_*_km=null`, neutral remoteness 0.5, evidence `layer_flags` — never `-1` / `999` sentinels |
| Legacy `seeds.geojson` | Runtime may still load seeds-only with a warning when `allow_legacy_seeds=True`; CI/`check_pack` rejects dual-path and seeds-only unless `--allow-legacy-seeds` |
| Invalid catalog | `load_pack_data(..., strict=True)` raises `CatalogValidationError` — no silent property fill |

## MissionIntent repairs

Unsafe LLM JSON is sanitized (`drop` unknown prefs/goals, clip to [-1, 1]). Semantic repairs land on `MissionIntent.intent_repairs` (and mirrored `interpreter_notes`). Unrecoverable cases (e.g. `days <= 0`) raise `IntentValidationError` and fail closed.

## Feature ranges

Unit-interval features on `CandidateFeatures` (`remoteness`, `crowd`, …) are always in **[0, 1]** (Pydantic-enforced). Distance fields are non-negative kilometers or **`null`** when the supporting pack layer is empty.

Propose changes via an RFC under the repository `RFC/` directory
([RFC index](https://github.com/OmarFarooq908/TerraQuest/blob/main/RFC/README.md)).
