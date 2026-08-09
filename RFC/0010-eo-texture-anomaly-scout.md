# RFC-0010: EO texture anomaly scout (pack feeder)

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-08
- Tracking issue / discussion: —

## Summary

Add an **optional, pack-time** discovery path for Earth-observation (EO)
**texture anomalies**: a standalone offline scout scans a local GeoTIFF, exports
candidate points for **human triage**, and a named generator
(`eo_texture_anomaly`) imports only **verified** points into the Region Pack
catalog. Mission runtime still never invents coordinates from imagery.

This is a **feeder pipeline**, not an archaeological detector. Edge/texture
contrasts are noisy; false positives from ridges, shadows, snow, and fields are
expected until a human verifies candidates (e.g. in Google Earth).

## Motivation

OSM + DEM generators miss unmapped surface signatures. Contributors want to hunt
remote EO anomalies (e.g. northern Pakistan AOIs) without violating the
architecture rule that LLM / VLM / Sentinel paths must not invent catalog nodes
at **mission** time. A standalone scout → verified GeoJSON → pack build fits
the existing generator contract (same class as `dem_local_max`).

## Hard rules

```text
Scout (offline, outside mission) → raw GeoJSON/GPX (verified=false)
Human triage → verified GeoJSON (verified=true)
Pack build generator → catalog candidates
Mission run → filter + score catalog only
```

Forbidden:

- Mission-time EO/LLM inventing lon/lat or catalog ids
- Ranking by “ruin score” from the scout
- Claiming edges = archaeology / buried walls in product copy
- Committing raw GeoTIFFs or unverified scout dumps into git

## Detailed design

### 1. Standalone scout

CLI: `scripts/eo_anomaly_scout.py` (library:
`adventure_packbuilder.eo_anomaly`).

Inputs: local multi-band GeoTIFF (NIR + SWIR for NDMI, or single-band fallback).
Deps: `rasterio` + `numpy` only (no rioxarray/scipy required).

Pipeline: index → Sobel-style edge magnitude → threshold → connected components
→ size filter → georeferenced Point features.

Outputs:

| Artifact | Role |
|----------|------|
| `*.geojson` | Point FC; `verified: false` by default |
| `*.gpx` (optional) | Waypoints for Google Earth / GPS triage |

### 2. Scout GeoJSON properties (raw)

| Property | Type | Notes |
|----------|------|-------|
| `id` | string | Stable scout id |
| `verified` | bool | Import requires `true` |
| `pixel_size` | int | Cluster pixel count |
| `edge_intensity` | float | Magnitude at cluster center |
| `index_name` | string | e.g. `ndmi` |
| `scout_version` | string | e.g. `eo_texture_anomaly_v1` |
| `raster` | string | Source filename (not full secrets path required) |

### 3. Generator `eo_texture_anomaly`

Pack config (opt-in):

```yaml
eo_scout:
  enabled: false
  candidates_geojson: data/cache/eo/skardu_v1_scout_verified.geojson

discovery:
  generators:
    eo_texture_anomaly: { quota: 20, min_spacing_km: 0.8 }
```

Default quota **0** so existing packs are unchanged. When enabled, pack build
loads the GeoJSON, keeps only `verified: true` points inside bbox, and emits
`CatalogCandidate` rows with evidence ledger keys:

`discovery_score`, `dist_settlement_km`, `pixel_size`, `edge_intensity`,
`index_name`.

Provenance: `sources` include `eo` (and/or `sentinel2` when the raster is
Sentinel-derived), `method: eo_texture_anomaly_v1`, `layer: eo_scout`.

### 4. Threats to validity

- High-contrast edges ≠ man-made structures.
- Alpine DEM shadows and snow lines dominate many AOIs.
- Pixel-size heuristics are resolution-dependent.
- Unverified import would pollute discovery eval — hence verified-only.

## Impact on contracts

- [ ] MissionIntent schema
- [x] Catalog schema / generators (`eo_texture_anomaly`)
- [x] Pack manifest (`eo_scout`, `PackSource.kind: eo`)
- [x] CLI UX (maintainer script; not mission flags)
- [ ] None (docs/process only)

## Alternatives considered

| Alt | Why not |
|-----|---------|
| Mission-time densify from imagery | Violates invent-at-runtime rule |
| Attach EO as evidence-only (like RFC-0006) | Does not create new places |
| Auto-import unverified scout output | Too noisy for North Star eval |
| Cloud vision “ruin detector” | Out of scope; local-first |

## Reproducibility & attribution

- Do not vendor full scenes in git; cache under `data/cache/eo/` (gitignored).
- When using Copernicus Sentinel, cite ESA / Copernicus in pack `NOTICE` and
  `sources[]`.
- Scout metrics land in catalog `evidence`; raster bytes are not part of
  `content_hash` unless copied into a pack layer (v1 does not copy rasters).

## Migration / compatibility

Additive. Packs without `eo_scout` behave as today. Fixture packs add one
synthetic `eo_texture_anomaly` feature for generator coverage.

## Unresolved questions

- Whether a later STAC snippet downloader belongs in-tree or as docs-only.
- Whether ranking should ever weight `edge_intensity` (needs eval lift first).
