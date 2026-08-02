# Pack builder

Production packs use **Geofabrik + osmium** (requires `osmium-tool` on PATH).
Architecture freeze: [RFC-0003](https://github.com/OmarFarooq908/TerraQuest/blob/main/RFC/0003-region-pack-architecture.md).

```bash
uv run adventurectl pack build --config skardu_v1
uv run python scripts/check_pack.py data/packs/skardu_v1
```

**Do not commit** `data/packs/`, `data/cache/`, PBF, or DEM tiles. Use
`fixtures/karakoram_mini` for offline CI.

## Outputs (`data/packs/<id>/`)

| Path | Purpose |
|------|---------|
| `layers/catalog.geojson` | Canonical discovery catalog |
| `layers/*.geojson` | Settlements, water, roads, peaks, viewpoints, DEM samples |
| `pack.yaml` | Manifest + honesty metadata + `layers:` map + `content_hash` |
| `NOTICE` | OSM ODbL + Copernicus attribution (required for real packs) |
| `build_stats.json` | OSM meta, discovery counts, DEM tiles, `content_hash` |
| `raw/` | Build cache only (optional; still under gitignored `data/packs/`) |

`layers/seeds.geojson` is **removed**. Packs that still ship both `catalog.geojson`
and `seeds.geojson` fail `scripts/check_pack.py` unless `--allow-legacy-seeds`.

### Manifest `layers:` map

Production builds list every shipped GeoJSON:

`settlements`, `water`, `road_nodes`, `road_lines`, `peaks`, `viewpoints`,
`catalog`, `elevation`. Optional: `sentinel_indices` (RFC-0006) when the layer is
written.

## Sentinel-2 indices (RFC-0006 / issue #21)

Opt-in EO indices (NDVI / NDWI) sampled at catalog points. **Default off** —
packs stay OSM + DEM only.

```yaml
# configs/packs/skardu_v1.yaml
sentinel2:
  enabled: false
  max_cloud_cover: 20
  indices: [ndvi, ndwi]
  indices_geojson: data/cache/sentinel2/skardu_v1_indices.geojson  # when enabling
```

### Skardu pilot steps

1. Build the OSM+DEM pack: `uv run adventurectl pack build --config skardu_v1`.
2. Query [Earth Search](https://earth-search.aws.element84.com/v1) `sentinel-2-l2a`
   for the pack bbox, `eo:cloud_cover ≤ 20`, prefer a recent low-cloud item; record
   `stac_item_id`.
3. Sample B03/B04/B08 at each catalog lon/lat; write a Point FeatureCollection with
   `catalog_id`, `ndvi`, `ndwi`, `cloud_cover`, `acquired_at`, `stac_item_id`,
   `index_version: s2-indices-v1` under `data/cache/sentinel2/` (gitignored).
4. Set `sentinel2.enabled: true` and `indices_geojson` to that path; rebuild.
5. Confirm `NOTICE` cites Copernicus Sentinel; `layers:` lists `sentinel_indices`.
6. Run discovery eval vs the GIS-only baseline; publish the delta (RFC-0005 metrics)
   even if lift is zero or negative. Ranking weights stay unchanged until then.

Live STAC download inside `pack build` is intentionally not wired yet — attach a
precomputed GeoJSON so CI stays offline.

Synthetic fixture smoke: `fixtures/karakoram_mini/layers/sentinel_indices.geojson`
(not real EO).

## Hashes (RFC-0003)

| Name | Covers |
|------|--------|
| Pack `content_hash` | All `layers/*.geojson` + `discovery.selected_by_generator` (SHA-256 → 16 hex) |
| `sources[].content_hash` | Per OSM/DEM artifact |
| Fixture `catalog.sha256` | Catalog file only (full SHA-256) |

`adventure_gis.pack_content_hash` accepts discovery stats **or** a full
`build_stats.json` blob (normalized via `.discovery`).

## Catalog validation

Required Feature `properties` (schema `0.3.0`):

| Field | Notes |
|-------|--------|
| `id`, `name`, `generator` | Identity + named discovery generator |
| `provenance` | `{sources, method, layer/dem_tile, …}` — `method` + non-empty `sources` |
| `evidence` | Object with **generator-family required keys** (evidence ledger v1) — empty `{}` fails |
| `densify` | `{cell_id, parent_id, densify_allowed, grid_res_deg}` — reserved for Phase C; no runtime densify yet |
| geometry | GeoJSON `Point` with lon/lat in range |

See [generators](generators.md) for the per-generator evidence contract
(`adventure_core.evidence_ledger`).

```bash
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run python scripts/check_pack.py data/packs/skardu_v1
```

Failure modes: missing required fields, out-of-range coordinates, dual-path
catalog+seeds, missing `NOTICE` / incomplete `layers:` map on real packs,
`content_hash` mismatch when declared on the manifest.

## Versioning

| Change | Bump |
|--------|------|
| Quotas, bbox, DEM/OSM refresh | Same `pack_id`; new `content_hash` |
| Breaking catalog feature contract | `feature_schema_version` / `CATALOG_SCHEMA_VERSION` (RFC) |
| Clean break of published pack identity | New `pack_id` (`skardu_v1` → `skardu_v2`) |

## OSM backends

| Method | Status | Notes |
|--------|--------|-------|
| `geofabrik` / `osmium` / `pbf` | **Production** | LineStrings for track_terminus / road_spur |
| `overpass` | **Degraded** | Requires `osm.allow_degraded_overpass: true`; no road_lines |

## Derived query DB (RFC-0004)

Optional DuckDB materialization for offline SQL / eval joins. GeoJSON stays the
source of truth; `query.duckdb` is gitignored and rebuilt from layers.

```bash
uv run adventurectl pack materialize --pack fixtures/karakoram_mini
uv run adventurectl pack query --pack fixtures/karakoram_mini \
  --sql "SELECT generator, count(*) AS n FROM catalog GROUP BY 1 ORDER BY n DESC"

# Eval harness opt-in join stats
uv run python scripts/eval_discovery.py --duckdb-join
```

Stale DBs (content hash mismatch) are regenerated automatically on `pack query`.
