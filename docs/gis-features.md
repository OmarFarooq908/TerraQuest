# GIS feature engineering

Mission-time features are computed by `adventure_gis.candidates.generate_candidates`
from Region Pack layers. They are **deterministic** and pack-reproducible (same
pack + vehicle/days → same features).

See issue [#23](https://github.com/OmarFarooq908/TerraQuest/issues/23).

## Inventory (current vs desired)

| Signal | Status | Source |
|--------|--------|--------|
| `dist_settlement_km` / `remoteness` | Shipping | Haversine to `settlements.geojson` |
| `dist_road_km` / `access_fit` | Shipping (+ **road class**) | Nearest `road_nodes` + `highway=*` |
| `dist_water_km` / `water` | Shipping | Haversine to water points (centroids) |
| `settlement_density` / crowd blend | **New (#23)** | Density kernel over settlements |
| `elevation_m` / `relief_m` / `terrain_drama` | Shipping | Catalog props + elevation samples |
| `forest` / `crowd` catalog props | Shipping | Hand props; crowd now blended with GIS density |
| True DEM prominence / ridges | Deferred | Needs raster morphology |
| Water/forest **edge** geometries | Deferred | Needs polygon layers |
| Road routing reachability | Deferred | P2 access epic |

## New features (#23 slice)

### Settlement density kernel

- **Definition:** Population-weighted, distance-decayed count of settlements within
  **10 km**, normalized by a reference weight of **4.0** and clamped to `[0, 1]`.
- **Data:** `layers/settlements.geojson` (`population` optional).
- **Scoring impact:** Blends into `crowd` (70% GIS / 30% catalog) and novelty’s
  anti-density term when the settlements layer is present. Empty layer → catalog
  props only; `settlement_density` / `settlements_within_10km` are `null`.
- **Evidence:** `settlement_density`, `settlements_within_10km`.

### Road-class access

- **Definition:** `access_fit` still uses distance buckets, then multiplies by an
  OSM `highway=*` quality score. Light vehicles (sedan/hatchback) are penalized
  harder for `track`/`path` nodes; capable `suv`/`4x4` less so.
- **Data:** `layers/road_nodes.geojson` → `highway`.
- **Evidence:** `nearest_highway` on the candidate.

## Eval note

On `evaluation/fixtures/karakoram_mini` with the standard hate-crowds / Swift prompt,
post-change metrics matched the pinned baseline (`recall@5=0.5`, `precision@5=1.0`,
same top ids). Synthetic labels are a smoke signal only — re-check on real regional
labels before treating density/road-class weights as final.
