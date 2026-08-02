# RFC-0003: Region Pack architecture freeze

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/18

## Summary

Freeze the **Region Pack on-disk contract**: directory layout, layer roles, `NOTICE`,
`build_stats.json`, content hashes, catalog schema vs pack-id versioning, and
Phase C `densify` hooks. Align contributor docs so a new pack builder can ship
Skardu-class packs without tribal knowledge.

## Motivation

Pack build works, but contributors currently reverse-engineer `build.py`, fixture
quirks, and Discord lore to answer:

- What files are required vs optional vs gitignored?
- What does `content_hash` actually cover?
- When do I bump `feature_schema_version` vs create `skardu_v2`?
- What may `densify` contain today without implying runtime densification?

Without a freeze, dual-path seeds, incomplete `layers:` maps, and mismatched hash
callers (eval vs `validate_pack`) will keep regenerating as “drive-by fixes.”

## Detailed design

### 1. On-disk contract

#### Production pack (`data/packs/<pack_id>/`) — **never commit**

```text
data/packs/<pack_id>/
  pack.yaml              # honesty manifest (required)
  NOTICE                 # OSM ODbL + Copernicus (required for synthetic=false)
  build_stats.json       # osm + discovery + dem_tiles + content_hash (required when content_hash set)
  layers/
    catalog.geojson      # canonical discovery candidates (required)
    settlements.geojson
    water.geojson
    road_nodes.geojson
    road_lines.geojson
    peaks.geojson
    viewpoints.geojson
    elevation.geojson
  raw/                   # build cache only (optional; gitignored with pack tree)
    osmium/ | overpass.json
    dem/*.tif
```

| Path | Role | Required |
|------|------|----------|
| `pack.yaml` | Manifest: `pack_id`, bbox, `feature_schema_version`, `synthetic`, `sources`, `content_hash`, `layers` map | Yes |
| `NOTICE` | Redistribution / attribution for OSM + DEM | Yes if `synthetic: false` |
| `build_stats.json` | Reproducibility + hash verification input | Yes if `content_hash` declared |
| `layers/catalog.geojson` | Discovery catalog (schema `0.3.0`) | Yes |
| Support GeoJSON layers | Featurization + generators | Yes for production builds |
| `raw/` | Intermediate downloads; not part of the shipped pack story | Optional |

**Do not commit** `data/packs/`, `data/cache/`, PBF, or DEM tiles (`.gitignore` +
CONTRIBUTING + PR template). CI never uploads built packs.

`scripts/check_pack.py` / `validate_pack` **enforce** for `synthetic: false`:

- `NOTICE` present
- `layers:` map lists all `REQUIRED_PACK_LAYER_KEYS` (including peaks/viewpoints)
- every non-legacy `layers/*.geojson` on disk appears in the map
- `content_hash` matches `pack_content_hash` when declared

#### Synthetic fixture pack (`fixtures/<id>/`) — committed

```text
fixtures/<id>/
  pack.yaml                 # synthetic: true; usually no content_hash / NOTICE
  catalog.sha256            # full SHA-256 of layers/catalog.geojson only (optional pin)
  layers/*.geojson          # including catalog + support layers
```

Fixtures are CI/offline only. They may omit `NOTICE`, `sources`, and pack
`content_hash`. Prefer `catalog.sha256` for catalog-byte pins.

### 2. `pack.yaml` `layers:` map

The manifest `layers:` map **must list every shipped GeoJSON** under `layers/`
that the builder writes for production packs, including `peaks` and `viewpoints`.
Files present on disk but missing from the map are a contract violation for new
builds (legacy packs may still omit them until rebuild).

Canonical keys:

`settlements`, `water`, `road_nodes`, `road_lines`, `peaks`, `viewpoints`,
`catalog`, `elevation`.

### 3. Hash glossary

| Name | Where | Covers | Encoding |
|------|--------|--------|----------|
| **Pack `content_hash`** | `pack.yaml` + `build_stats.json` | Domain-separated **pack-content v2**: all `layers/*.geojson` (name + bytes, sorted) **plus** a stable discovery subset (see below) | SHA-256 truncated to **16 hex** |
| **`layer_digests`** | `build_stats.json` | Per-file full SHA-256 of each `layers/*.geojson` (audit; not the pack fingerprint) | Full SHA-256 hex |
| **`PackSource.content_hash`** | Each `sources[]` entry | OSM filtered PBF / Overpass JSON, or DEM tile concat | 16 hex |
| **Eval `pack_content_hash`** | `scripts/eval_discovery.py` reports | Same function as pack `content_hash` | 16 hex |
| **Fixture `catalog.sha256`** | `fixtures/.../catalog.sha256` | **Only** `layers/catalog.geojson` full file | Full SHA-256 |

Implementation: `adventure_gis.pack_hash.pack_content_hash`
(`PACK_CONTENT_HASH_VERSION`, domain prefix `terraquest-pack-content-v2\0`).

**Discovery subset folded into the pack fingerprint** (keys hashed when present):

`selected_by_generator`, `quotas`, `min_spacing_km`, `grid_res_deg`,
`catalog_schema_version`, `generators_run` (list values sorted for stability).

**Stats object for hashing:** always the **discovery stats** dict. Callers may
pass either:

1. Discovery stats directly (pack builder), or
2. A full `build_stats.json` blob — normalized by extracting `.discovery`.

`validate_pack` and eval fingerprints **must** agree after normalization.
Production builds also record `pack_content_hash_version` and `layer_digests`
alongside `content_hash` in `build_stats.json`.

Leftover `layers/seeds.geojson` **changes** the pack hash. Dual-path packs fail
`check_pack` unless `--allow-legacy-seeds` (legacy escape hatch; rebuild to remove).

### 4. `build_stats.json` shape

```json
{
  "osm": { "...ingest meta..." },
  "discovery": {
    "catalog_schema_version": "0.3.0",
    "catalog_count": 0,
    "with_dem_elevation": 0,
    "raw_by_generator": {},
    "selected_by_generator": {},
    "quotas": {},
    "min_spacing_km": 0,
    "grid_res_deg": 0.02,
    "generators_run": []
  },
  "dem_tiles": ["..."],
  "content_hash": "0123456789abcdef",
  "pack_content_hash_version": 2,
  "layer_digests": {
    "catalog.geojson": "<64-hex sha256>",
    "peaks.geojson": "<64-hex sha256>"
  }
}
```

### 5. Versioning policy

| Change | Action |
|--------|--------|
| Bbox, quotas, spacing, notes, DEM/OSM refresh | Keep `pack_id`; new `content_hash` / `built_at` / source hashes |
| Additive optional evidence keys; new support layer **files** already allowed by loaders | No catalog schema bump if existing features remain valid |
| Required catalog property added/removed/renamed; densify required fields change; geometry rules change | Bump `CATALOG_SCHEMA_VERSION` / `feature_schema_version` (e.g. `0.3.0` → `0.4.0`) via RFC |
| Incompatible region definition or intentional clean break of published pack identity | New `pack_id` (`skardu_v1` → `skardu_v2`) |

`pack_id` is the **artifact identity**. `feature_schema_version` is the **catalog
feature contract**. Both appear on the manifest; non-synthetic packs must match
the code constant `CATALOG_SCHEMA_VERSION`.

### 6. Densify hooks (Phase C reserved)

Every catalog feature carries:

```text
densify: { cell_id, parent_id, densify_allowed, grid_res_deg }
```

Today: writers populate these at pack build; **mission runtime must not densify**.
Changing required densify fields is a catalog schema bump. Enabling Phase C
runtime densification requires its own RFC and must not alter `MissionIntent`.

### 7. NOTICE minimum (production)

Must name: pack id, built timestamp, bbox, catalog schema, OSM ODbL with URL,
Copernicus DEM attribution with URL, and a one-line note that candidates come from
named deterministic generators under ODbL share-alike for OSM-derived products.

Synthetic fixtures are exempt from pack-level NOTICE.

### 8. Contributor build path (Skardu-class)

```bash
brew install osmium-tool   # or equivalent
uv sync --group dev
uv run adventurectl pack build --config skardu_v1
uv run python scripts/check_pack.py data/packs/skardu_v1
uv run adventurectl mission run --pack skardu_v1 --interpreter rules -p "..."
```

Never add `data/packs/**` to git. Use `fixtures/karakoram_mini` for offline CI.

## Impact on contracts

- [ ] MissionIntent schema
- [x] Catalog schema / generators (documents freeze; no bump in this RFC)
- [x] Pack manifest (`layers:` map completeness; hash normalization)
- [ ] CLI UX
- [x] Docs/process (`docs/pack-builder.md`, `docs/architecture.md`, RFC index)

## Alternatives considered

1. **Hash only `catalog.geojson`** — simpler, but support-layer drift would be invisible to eval pins.
2. **Full SHA-256 in manifests** — noisier diffs; 16-hex is enough for collision resistance in this trust model.
3. **Require NOTICE on fixtures** — rejected; synthetic packs must stay obviously non-production.

## Reproducibility & attribution

OSM: ODbL share-alike for derived databases/products. DEM: Copernicus terms via
pack `NOTICE`. Fixtures: Apache-2.0 synthetic GeoJSON, not survey-grade.

## Migration / compatibility

- Rebuild production packs after accepting this RFC so `layers:` includes peaks/viewpoints.
- Dual-path `seeds.geojson`: keep `--allow-legacy-seeds` until known packs rebuild; then remove in a follow-up.
- Eval reports that hashed full `build_stats` blobs without reading `.discovery`
  may change fingerprint once normalization lands — regenerate reports if needed.
- **Pack-content hash v2** (#62): fingerprints change vs v1 even for identical layer
  bytes (domain separator + broader discovery subset). Rebuild packs / retarget
  eval pins after upgrading; `build_stats.json` gains `pack_content_hash_version`
  and `layer_digests`.
- Stale local packs (missing peaks/viewpoints in `layers:`, leftover `seeds.geojson`)
  fail `check_pack` until rebuilt with the current packbuilder.

## Unresolved questions

1. Timeline to delete `--allow-legacy-seeds` after known public packs rebuild.
2. Whether `raw/` should be wiped by default after a successful build (disk hygiene).
3. Whether fixture packs should eventually declare a pack-level `content_hash` (today: `catalog.sha256` only).
