# RFC-0004: DuckDB local query layer over Region Packs

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/20

## Summary

Add an **optional, derived** DuckDB database (`query.duckdb`) next to a Region Pack’s
GeoJSON layers for spatial-ish joins, generator analytics, and eval label joins.
GeoJSON remains the interchange / source of truth; pack rebuild (or explicit
`pack materialize`) regenerates the DB and pins it to `content_hash`.

## Motivation

Catalog FeatureCollections are honest and git-friendly, but awkward for:

- Counting / grouping by `generator`
- Joining catalog ids to evaluation labels at scale
- Ad-hoc offline SQL during research

A cloud warehouse is out of scope. DuckDB is local, embeddable, and offline-friendly
once installed via the workspace dependency.

## Detailed design

### Artifact

```text
<data/packs/<id>|fixtures/<id>>/
  pack.yaml
  layers/*.geojson          # source of truth
  query.duckdb              # DERIVED — gitignored; never commit
```

| Property | Rule |
|----------|------|
| Name | Always `query.duckdb` at the pack root |
| Source of truth | `layers/*.geojson` (+ discovery stats for hash) |
| Sync | Table `_pack_meta.content_hash` must match `pack_content_hash(...)` |
| Rebuild | `adventurectl pack materialize` or auto on `pack query` when stale |

### Schema (v1)

Tables (one per GeoJSON FeatureCollection file stem):

| Table | Columns |
|-------|---------|
| `catalog`, `settlements`, `water`, `road_nodes`, … | `id TEXT`, `name TEXT`, `lon DOUBLE`, `lat DOUBLE`, `generator TEXT` (catalog), `properties JSON`, `geometry_type TEXT` |
| `_pack_meta` | `pack_id`, `content_hash`, `feature_schema_version`, `materialized_at`, `duckdb_schema_version` |

No PostGIS / DuckDB `spatial` extension required in v1 (lon/lat columns only). Haversine
joins stay in Python or SQL expressions.

`duckdb_schema_version`: `"1"`.

### CLI

```bash
# Rebuild derived DB (idempotent; skips when hash matches unless --force)
uv run adventurectl pack materialize --pack fixtures/karakoram_mini

# Read-only SQL (auto-materializes if missing/stale)
uv run adventurectl pack query --pack fixtures/karakoram_mini \
  --sql "SELECT generator, count(*) AS n FROM catalog GROUP BY 1 ORDER BY n DESC"
```

### Eval harness

`adventure_gis.pack_query.connect_pack_db` / `catalog_label_join_counts` helpers let
`scripts/eval_discovery.py` (and tests) join `catalog.id` to label `catalog_id`
without scanning GeoJSON in nested Python loops when desired. Default eval path
may stay Python-native; DuckDB is opt-in via `--duckdb-join` or library use.

Hard guarantees: `pack query` opens the DB **read-only** and rejects multi-statement
batches / obvious write leads. Soft keyword checks are defense-in-depth only.

### Hash coupling (RFC-0003)

Materialization records the same 16-hex `pack_content_hash` used on production
manifests. Stale DB → rebuild. Fixtures without manifest `content_hash` still
fingerprint layers via `pack_content_hash(layers_dir)`.

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators
- [x] Pack manifest (derived sibling file only; GeoJSON unchanged)
- [x] CLI UX (`pack materialize`, `pack query`)
- [x] Docs/process (RFC-0004, pack-builder)

## Alternatives considered

1. **SQLite + SpatiaLite** — heavier native deps on some platforms; DuckDB wheels are simpler for uv CI.
2. **Replace GeoJSON with DuckDB as interchange** — rejected for v1 (RFC-0003 freeze; git-friendly layers).
3. **Parquet only** — good for analytics, weaker for interactive SQL + single-file UX.

## Reproducibility & attribution

DB contains only derived copies of pack layers already covered by pack `NOTICE` /
fixture licenses. Do not distribute `query.duckdb` as a substitute for GeoJSON + NOTICE.

## Migration / compatibility

- Add `**/query.duckdb` to `.gitignore`.
- No change to existing mission scoring path.
- Optional dependency surface: `duckdb` on `adventure-gis`.

## Unresolved questions

1. Whether `pack build` should auto-materialize `query.duckdb` at the end of production builds.
2. When to enable DuckDB `spatial` for true geometry predicates (needs careful offline install story).
