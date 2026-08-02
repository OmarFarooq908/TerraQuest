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

`layers/seeds.geojson` is a temporary alias of the catalog (deprecated).

## OSM backends

| Method | Status | Notes |
|--------|--------|-------|
| `geofabrik` / `osmium` / `pbf` | **Production** | LineStrings for track_terminus / road_spur |
| `overpass` | **Degraded** | Requires `osm.allow_degraded_overpass: true`; no road_lines |

## Discovery config

See `configs/packs/skardu_v1.yaml` → `discovery.generators` for per-generator quotas and spacing. There is no global `max_total` cap.
