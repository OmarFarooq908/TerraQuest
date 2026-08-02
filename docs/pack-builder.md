# Pack builder

Production packs use **Geofabrik + osmium** (requires `osmium-tool` on PATH).

```bash
uv run adventurectl pack build --config skardu_v1
```

## Outputs (`data/packs/<id>/`)

| Path | Purpose |
|------|---------|
| `layers/catalog.geojson` | Canonical discovery catalog |
| `layers/*.geojson` | Settlements, water, roads, DEM samples |
| `pack.yaml` | Manifest + honesty metadata |
| `NOTICE` | OSM ODbL + Copernicus attribution |
| `build_stats.json` | Generator raw/selected counts |

`layers/seeds.geojson` is **removed**. Packs that still ship both `catalog.geojson` and `seeds.geojson` fail `scripts/check_pack.py` unless `--allow-legacy-seeds` is passed.

## Catalog validation

Required Feature `properties` (schema `0.3.0`):

| Field | Notes |
|-------|--------|
| `id`, `name`, `generator` | Identity + named discovery generator |
| `provenance` | `{sources, method, …}` — `method` required |
| `evidence` | Object (may be empty) |
| `densify` | `{cell_id, parent_id, densify_allowed, grid_res_deg}` |
| geometry | GeoJSON `Point` with lon/lat in range |

```bash
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run python scripts/check_pack.py data/packs/skardu_v1
```

Failure modes: missing required fields, out-of-range coordinates, dual-path catalog+seeds, `content_hash` mismatch when declared on the manifest.

## OSM backends

| Method | Status | Notes |
|--------|--------|-------|
| `geofabrik` / `osmium` / `pbf` | **Production** | LineStrings for track_terminus / road_spur |
| `overpass` | **Degraded** | Requires `osm.allow_degraded_overpass: true`; no road_lines |

## Discovery config

See `configs/packs/skardu_v1.yaml` → `discovery.generators` for per-generator quotas and spacing. There is no global `max_total` cap.
