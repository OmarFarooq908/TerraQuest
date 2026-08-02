# RFC-0006: Sentinel-2 indices in Region Packs

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/21

## Summary

Add an **optional** Region Pack layer of Sentinel-2-derived indices (minimal set:
**NDVI**, **NDWI**) sampled at catalog points, cited in candidate evidence, and
exposed on mission-time `CandidateFeatures` — **without** letting an LLM invent
places or changing default ranking weights until evaluation lift is measured.

v1 packs remain valid without this layer (`ndvi`/`ndwi` stay `null`).

## Motivation

Known limit: packs are OSM + DEM only. Vegetation / surface-water signals would
improve forest/water/crowd proxies with open, reproducible Earth observation —
aligned with local-first, no cloud LLM ranking.

## Detailed design

### 1. STAC / source choice

| Choice | Decision |
|--------|----------|
| **Primary STAC** | [Element84 Earth Search](https://earth-search.aws.element84.com/v1) (`sentinel-2-l2a`) — open, no account for STAC browse; COGs on AWS Open Data |
| **Alt** | Microsoft Planetary Computer STAC (same collection family; needs token for some assets) |
| **Product** | Sentinel-2 L2A surface reflectance |
| **Bands (minimal)** | B04 (red), B08 (NIR) → NDVI; B03 (green), B08 → NDWI |
| **License / attribution** | Copernicus Sentinel data — cite ESA / Copernicus in pack `NOTICE` + `sources[]` (`kind: sentinel2`) |

Do **not** vendor full scenes into git. Cache under `data/cache/sentinel2/` (gitignored).

### 2. Cloud cover + revisit policy

| Knob | Default | Notes |
|------|---------|-------|
| `max_cloud_cover` | **20** (%) | Scene-level `eo:cloud_cover` from STAC |
| Date window | Last **18 months** before build, prefer lowest cloud | Pin `retrieved_at` + chosen `stac_item` ids in layer props / source `extra` |
| Mosaic | **Single best scene per AOI** for v1 (not multi-date composite) | Keeps reproducibility simpler |
| Fail closed | If no scene under cloud cap → **skip layer** (pack still builds); log clearly | Never invent index values |

### 3. Storage + size budget

| Artifact | Format | Budget |
|----------|--------|--------|
| Pack layer | `layers/sentinel_indices.geojson` (Point FC) | Prefer **≪ 5 MB** for Skardu-class catalog (~100–200 pts) |
| Raw COG cache | `data/cache/sentinel2/` | Not part of pack hash; local only |
| Full tiles in pack | **Out of scope** for v1 | Optional later as COG under `raw/` |

**Sampling mode (v1):** values at **catalog point** coordinates (point sample /
bilinear on 10 m bands). Not tile grids in the shipped pack.

### 4. Layer schema (`sentinel_indices`)

Optional key in `pack.yaml` `layers:` map (not in `REQUIRED_PACK_LAYER_KEYS`):

```text
sentinel_indices → layers/sentinel_indices.geojson
```

Each feature:

| Property | Type | Required |
|----------|------|----------|
| `catalog_id` | string | Yes (join key to catalog) |
| `ndvi` | float \| null | Yes (null if masked/nodata) |
| `ndwi` | float \| null | Yes |
| `cloud_cover` | float \| null | Scene % when known |
| `acquired_at` | string \| null | ISO date of scene |
| `stac_item_id` | string \| null | Repro pin |
| `index_version` | string | e.g. `s2-indices-v1` |

Geometry: Point (same lon/lat as catalog feature). Indices in **[-1, 1]**.

When the file is present on a **production** pack, it **must** appear in the
manifest `layers:` map (RFC-0003 hygiene). Absence is normal for v1 packs.

### 5. Pack build hook

`configs/packs/*.yaml`:

```yaml
sentinel2:
  enabled: false          # opt-in
  max_cloud_cover: 20
  indices: [ndvi, ndwi]
  # Pilot path: point at a precomputed FeatureCollection (no network in CI)
  indices_geojson: null   # e.g. data/cache/sentinel2/skardu_v1_indices.geojson
```

Build behavior:

1. `enabled: false` → no layer (current default).
2. `enabled: true` + `indices_geojson` set → copy/normalize into
   `layers/sentinel_indices.geojson`, append `PackSource(kind=sentinel2, …)`,
   extend `layers:` map, append Sentinel attribution to `NOTICE`.
3. `enabled: true` without `indices_geojson` → fail with actionable message
   pointing at the Skardu pilot recipe (STAC → sample → GeoJSON). Live STAC
   download inside `pack build` is a follow-up behind the same flag.

### 6. Mission-time featurize

`load_pack_data` loads optional `sentinel_indices`.
`generate_candidates` joins by `catalog_id` (exact); if missing, nearest index
point within **0.25 km** (else null).

| Field | Behavior |
|-------|----------|
| `CandidateFeatures.ndvi` / `.ndwi` | `float \| null` in [-1, 1] |
| `evidence["ndvi"]`, `["ndwi"]`, `["sentinel"]` | Audit trail |
| `layer_flags.sentinel_indices_layer_empty` | `true` when layer absent/empty |

**Ranking (v1):** preference-vector weights **unchanged**. Indices are features +
evidence only until an eval delta justifies a blend (e.g. into `forest` / `water`).

### 7. Skardu pilot recipe (documented)

1. Build OSM+DEM pack as today: `adventurectl pack build --config skardu_v1`.
2. Query Earth Search for `sentinel-2-l2a` intersecting pack bbox, `eo:cloud_cover ≤ 20`,
   prefer recent; record `stac_item_id`.
3. Sample B03/B04/B08 at each catalog lon/lat; write GeoJSON with schema above to
   `data/cache/sentinel2/skardu_v1_indices.geojson`.
4. Set `sentinel2.enabled: true` + `indices_geojson: …` and rebuild (or copy layer
   + update `layers:` / `NOTICE` / re-hash).
5. Run `scripts/eval_discovery.py` vs GIS-only baseline; publish delta even if ≤ 0.

Synthetic fixture `fixtures/karakoram_mini` may ship a tiny synthetic
`sentinel_indices.geojson` for CI smoke (not real EO).

### 8. Eval honesty

| Condition | Expected |
|-----------|----------|
| Layer absent | Features null; ranking identical to pre-RFC packs |
| Synthetic fixture layer | Features populated; **ranking unchanged** until weights enabled |
| Skardu pilot + weights off | Report feature coverage + baseline metrics |
| After weight experiment | Report recall@k + popularity trap delta (RFC-0005) |

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators (catalog GeoJSON unchanged)
- [x] Pack manifest (`sentinel2:` build config; optional `layers.sentinel_indices`)
- [ ] CLI UX (no new mission flags)
- [x] Docs/process (RFC-0006, pack-builder, GIS features, known limits)
- [x] `CandidateFeatures` additive optional fields

## Alternatives considered

1. **Bake full COG tiles into packs** — size + license complexity; defer.
2. **Mission-time STAC fetch** — breaks offline CI and reproducibility; reject.
3. **VLM landcover instead** — issue #22; complementary, not a substitute.
4. **Change ranking immediately** — violates “measure lift first.”

## Reproducibility & attribution

- Pin `stac_item_id`, `acquired_at`, `index_version` on features + `sources[]`.
- Pack `content_hash` includes `sentinel_indices.geojson` when present.
- NOTICE must mention Copernicus Sentinel when the layer ships.

## Migration / compatibility

Additive. Existing packs and fixtures without the layer keep working.
Optional layer must be listed in production `layers:` maps when on disk.

## Unresolved questions

1. Exact NDVI→`forest` / NDWI→`water` blend coefficients after first Skardu eval.
2. Whether multi-date medoid mosaics are worth the reproducibility cost.
3. Optional live STAC client dependency vs always “precompute then attach.”
