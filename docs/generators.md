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

- `provenance` — sources, method, osm_id / dem_tile
- `evidence` — discovery_score and measured distances
- `densify` — `cell_id` / `parent_id` reserved for Phase C

Quotas and `min_spacing_km` are applied per generator, then soft global merge.

## Testing

Offline unit tests live in `tests/test_generators.py` (synthetic GeoJSON layers, no
network / DEM). Prefer adding a focused case there when introducing a generator or
changing quota / spacing behavior.
