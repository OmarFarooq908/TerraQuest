# Discovery generators

Every catalog candidate must originate from a named generator.

| Generator | Evidence idea |
|-----------|----------------|
| `track_terminus` | Endpoints of track/path ways far from settlements |
| `road_spur` | Track with one end near drivable network, far end remote |
| `named_waterbody` / `unnamed_waterbody` | OSM water centroids |
| `isolation_maximum` | Grid local max of distance-to-settlement |
| `dem_local_max` | DEM elevation local maxima |
| `terrain_relief_hotspot` | High local relief windows |
| `osm_peak` / `osm_viewpoint` | OSM landmark nodes |
| `synthetic_fixture` | CI fixtures only |

The offline pack `fixtures/karakoram_mini` is hand-seeded and **SYNTHETIC**, but its
`layers/catalog.geojson` includes at least one feature for each shipping generator
name above (except `synthetic_fixture`, which is a schema alias for ad-hoc tests).
Supporting layers (`peaks`, `viewpoints`, `road_lines`, unnamed water, extra DEM
samples) exist for geometric consistency — mission ranking still reads the catalog.

Each feature stores:

- `provenance` — sources, method, osm_id / dem_tile / layer
- `evidence` — **ledger v2** required keys per generator (see below)
- `densify` — `cell_id` / `parent_id` reserved for Phase C

## Evidence ledger (v2)

`scripts/check_pack.py` / `validate_catalog_geojson` enforce
`adventure_core.evidence_ledger` (version string `2`):

| Generator family | Required `evidence` keys |
|------------------|--------------------------|
| `track_terminus` | `discovery_score`, `dist_settlement_km`, `endpoint` |
| `road_spur` | `discovery_score`, `dist_settlement_km`, `far_endpoint` |
| water (`named_` / `unnamed_`) | `discovery_score`, `dist_settlement_km`, `water_kind`, `named` |
| `osm_peak` / `osm_viewpoint` | `discovery_score`, `dist_settlement_km` |
| `isolation_maximum` | `discovery_score`, `dist_settlement_km`, `grid_res_deg` |
| `dem_local_max` | `discovery_score`, `dist_settlement_km`, `elevation_m` |
| `terrain_relief_hotspot` | `discovery_score`, `dist_settlement_km`, `relief_m` |
| `synthetic_fixture` | `discovery_score`, `fixture` |

Synthetic packs must set `evidence.fixture=true` whenever `provenance.sources`
includes `synthetic`. Real OSM/DEM packs must declare matching source kinds
(`osm` / `dem`) and DEM features need `provenance.dem_tile`.

**v2 provenance:** non-synthetic **OSM-element** generators
(`track_terminus`, `road_spur`, named/unnamed water, `osm_peak`,
`osm_viewpoint`) require `provenance.osm_id` as a positive int (integral
floats like `123.0` accepted for GeoJSON interop). Packbuilder skips
emitting those candidates when the source layer lacks a usable `osm_id`.
Grid `isolation_maximum` and DEM generators do **not** require `osm_id`.
DEM window polygons remain deferred.

Empty / whitespace ``generator`` values and blank string evidence fields
(e.g. ``water_kind: ""``) fail validation.
Quotas and `min_spacing_km` are applied per generator, then soft global merge.

## Testing

Offline unit tests live in `tests/test_generators.py` (synthetic GeoJSON layers, no
network / DEM). Prefer adding a focused case there when introducing a generator or
changing quota / spacing behavior.
