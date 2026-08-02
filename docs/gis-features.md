# GIS feature engineering

Mission-time features are computed by `adventure_gis.candidates.generate_candidates`
from Region Pack layers. They are **deterministic** and pack-reproducible (same
pack + vehicle/days → same features).

See issue [#23](https://github.com/OmarFarooq908/TerraQuest/issues/23) and
[#21](https://github.com/OmarFarooq908/TerraQuest/issues/21) (Sentinel-2).

## Inventory (current vs desired)

| Signal | Status | Source |
|--------|--------|--------|
| `dist_settlement_km` / `remoteness` | Shipping | Haversine to `settlements.geojson` |
| `dist_road_km` / `access_fit` | Shipping (+ **road class**) | Best *usable* `road_nodes` node (class×distance) + `highway=*` |
| `dist_water_km` / `water` | Shipping | Haversine to water points (centroids) |
| `settlement_density` / crowd blend | Shipping (#23) | Density kernel over settlements |
| `elevation_m` / `relief_m` / `terrain_drama` | Shipping | Catalog props + elevation samples |
| `forest` / `crowd` catalog props | Shipping | Hand props; crowd now blended with GIS density |
| `ndvi` / `ndwi` (Sentinel-2) | **Optional (#21 / RFC-0006)** | `layers/sentinel_indices.geojson` when present |
| True DEM prominence / ridges | Deferred | Needs raster morphology |
| Water/forest **edge** geometries | Deferred | Needs polygon layers |
| Road routing reachability | Deferred | P2 access epic |

## Settlement density kernel (#23)

- **Definition:** Population-weighted, distance-decayed count of settlements within
  **10 km**, normalized by a reference weight of **4.0** and clamped to `[0, 1]`.
- **Data:** `layers/settlements.geojson` (`population` optional).
- **Scoring impact:** Blends into `crowd` (70% GIS / 30% catalog) and novelty’s
  anti-density term when the settlements layer is present. Empty layer → catalog
  props only; `settlement_density` / `settlements_within_10km` are `null`.
- **Evidence:** `settlement_density`, `settlements_within_10km`.

## Road-class access (#23)

- **Definition:** Select an *access* road node by maximizing
  `effective_highway_class / (1 + dist_km / 5)` for the mission vehicle (so a
  nearby `path` does not beat a slightly farther `secondary` for sedans). Then
  apply distance buckets × class multipliers; light vehicles are penalized harder
  on `track`/`path`; capable `suv`/`4x4` less so.
- **Data:** `layers/road_nodes.geojson` → `highway`.
- **Fields / evidence:** `dist_road_km` + `nearest_highway` refer to the **selected
  access** node. Geometric nearest is also recorded as `dist_road_geom_km` /
  `nearest_highway_geom` in evidence for audit.

## Sentinel-2 indices (RFC-0006 / #21)

- **Definition:** Point-sampled NDVI / NDWI in **[-1, 1]** joined by `catalog_id`
  (else nearest unlabeled index point within 0.25 km — never a neighbor's
  `catalog_id` sample).
- **Data:** optional `layers/sentinel_indices.geojson` (not required for v1 packs).
- **Scoring impact:** **None yet** — features + evidence only; preference weights
  unchanged until Skardu eval justifies a blend.
- **Evidence:** `ndvi`, `ndwi`, `sentinel` meta, `layer_flags.sentinel_indices_layer_empty`.
- **Build:** `sentinel2.enabled` + precomputed `indices_geojson` (see pack-builder).

## Eval note

On `evaluation/fixtures/karakoram_mini` with the standard hate-crowds / Swift prompt,
GIS depth + optional synthetic Sentinel features still match the pinned baseline
(`recall@5=0.5`, `precision@5=1.0`) when ranking weights ignore NDVI/NDWI.
Synthetic labels are a smoke signal only — re-check on real regional labels before
treating density/road-class/Sentinel blends as final.
