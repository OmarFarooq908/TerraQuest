# RFC-0007: VLM feature extraction at pack build (not ranking)

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/22

## Summary

Allow **optional, pack-time** vision-language model (VLM) extraction of structured
scene / landcover attributes for catalog candidates. Outputs land in pack evidence
(versioned). **Ranking stays preference-vector over GIS (+ optional VLM) features** —
the VLM must never pick winners, invent coordinates, or emit free-form “best mission”
scores.

Default OSS path stays offline: flag off; CI never requires a VLM.

## Motivation

GIS distances and DEM relief miss “what the place looks like.” Local VLMs can label
terrain/landcover for candidates **after** discovery places exist. That fits
local-first science and keeps MissionIntent → deterministic scoring intact.

## Hard rule

```text
VLM → structured features / concept_ids → catalog evidence
Ranking = preference vector over features (GIS first; VLM additive later)
```

Forbidden:

- VLM choosing or ordering missions
- Inventing lon/lat or new catalog ids
- Cloud VLM as the default OSS/CI path
- Treating natural-language captions as scores

## Detailed design

### 1. Model options (local-first)

| Option | Role | Default? |
|--------|------|----------|
| **Ollama vision** (e.g. `llava`, `moondream`) | Pack-time labeler when live path lands | Preferred runtime |
| **Precomputed GeoJSON attach** | Pilot / CI / air-gapped builds | **v1 ship path** |
| Cloud VLMs (OpenAI/Anthropic/Google vision) | — | **Out of scope** as defaults |

Pins live in `configs/models.yaml` under `pack_vlm` (+ `hardware_floors`). Ollama
weights stay in Ollama’s store; Adventure caches only **outputs** under
`data/cache/inference/vlm/` (gitignored).

Approximate floors (guidance, not hard gates):

| Model class | Free RAM |
|-------------|----------|
| moondream-class | ≈ 4–6 GB |
| llava 7B-class | ≈ 8–12 GB |

### 2. Output schema (`vlm_features` layer)

Optional pack layer (not in `REQUIRED_PACK_LAYER_KEYS`):

```text
vlm_features → layers/vlm_features.geojson
```

Point FeatureCollection; one feature per labeled catalog id:

| Property | Type | Required |
|----------|------|----------|
| `catalog_id` | string | Yes |
| `vlm_version` | string | Yes (`vlm-features-v1`) |
| `model` | string | Yes (e.g. `llava:7b` or `synthetic-fixture`) |
| `concept_ids` | string[] | Yes (may be empty) |
| `attributes` | object | Yes (may be `{}`) |
| `confidence` | float \| null | No ∈ [0, 1] |
| `prompt_id` | string | Yes (e.g. `pack_vlm_v1`) |
| `image_ref` | string \| null | No (cache-relative path; never commit blobs) |

`concept_ids` should prefer keys from `adventure_core.ontology.CONCEPT_TO_DIMENSIONS`
until the formal ontology epic (#10) lands. Unknown ids are kept but flagged in
`attributes.unknown_concepts` at normalize time (not dropped silently).

### 3. Pack build hook

```yaml
# configs/packs/*.yaml
vlm:
  enabled: false
  features_geojson: null   # precomputed FC path when enabling
  model: llava             # documented pin for future live Ollama path
  prompt_id: pack_vlm_v1
```

Behavior:

1. `enabled: false` → remove leftover `vlm_features.geojson` if present; no source entry.
2. `enabled: true` + `features_geojson` → normalize, write layer, append honesty note,
   extend `layers:` map, record provider in `sources[]` / `build_stats.vlm`.
3. `enabled: true` without path → fail with actionable error (live Ollama vision
   fetch is a follow-up behind the same flag).

### 4. Mission-time use

`load_pack_data` loads optional `vlm_features`.
`generate_candidates` joins by `catalog_id` (exact only — no distance steal).

| Surface | Behavior |
|---------|----------|
| `evidence["vlm"]` | Full record (version, model, concepts, attributes, confidence) |
| `layer_flags.vlm_features_layer_empty` | true when layer absent/empty |
| Preference / score | **Unchanged in v1** |

Future blend (post-eval): map `concept_ids` through ontology into soft feature
nudges — only after RFC-0005 metrics show lift on regional labels.

### 5. Caching & failure modes

| Case | Action |
|------|--------|
| VLM timeout / Ollama down (live path) | Skip candidate; leave unlabeled; never invent |
| Malformed JSON from model | Reject record; fail attach if precomputed invalid |
| Missing image for a catalog id | Skip that id |
| Duplicate `catalog_id` in layer | Fail attach |
| Empty FeatureCollection | Fail attach when enabled |

Cache key (future live path):
`hash(catalog_id, prompt_id, model, image_bytes) → data/cache/inference/vlm/…`.

### 6. Bakeoff / eval honesty

| Condition | Expected |
|-----------|----------|
| Flag off / layer absent | Identical to GIS-only ranking |
| Synthetic fixture layer | Features in evidence; **ranking unchanged** |
| Skardu pilot + weights off | Report coverage + baseline recall@k / popularity trap |
| After weight experiment | Publish delta vs GIS-only (even if ≤ 0) |

Fixture smoke: optional synthetic `vlm_features.geojson` on `karakoram_mini`.

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators (catalog GeoJSON unchanged; evidence additive at mission time)
- [x] Pack manifest (`vlm:` build config; optional `layers.vlm_features`)
- [ ] CLI UX (mission flags unchanged; pack build errors on misconfig)
- [x] Docs/process (RFC-0007, offline-inference, pack-builder)
- [ ] Preference weights (deferred)

## Alternatives considered

1. **Mission-time VLM** — breaks offline CI reproducibility; reject for v1.
2. **VLM as ranker** — violates hard rule / ROADMAP.
3. **Wait for formal ontology (#10)** — blocks progress; use transitional concept ids.
4. **Cloud vision defaults** — rejected for OSS.

## Reproducibility & attribution

- Pin `vlm_version`, `model`, `prompt_id` on every feature.
- Pack `content_hash` includes `vlm_features.geojson` when present.
- Model weights: Ollama’s license; do not vendor weights into the repo.

## Migration / compatibility

Additive. Packs without the layer behave as today.
Production packs that ship the file must list it in `layers:`.

## Unresolved questions

1. Exact concept→feature blend after first bakeoff.
2. Whether DEM hillshade / Mapillary / static map tiles are the image source for live labeling.
3. Multi-VLM bakeoff harness layout under `evaluation/reports/`.
