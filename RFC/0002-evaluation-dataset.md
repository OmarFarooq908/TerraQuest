# RFC-0002: Evaluation dataset for discovery quality

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/9

## Summary

Introduce a versioned, offline **evaluation dataset** of human- (or curator-) rated places so we can measure whether discovery generators and scorers find *interesting* locations — not only whether ranking is deterministic. Ship a Pydantic schema, on-disk layout under `evaluation/`, and an offline metrics harness. CI uses a **synthetic** fixture-aligned slice; real regional labels are curated separately with explicit licenses.

## Motivation

Golden prompts prove intent signs and preference alignment. They cannot answer:

> Did generator A find something an experienced explorer would add to their list?

Without labeled places (interestingness vs popularity), research and pack changes are unfalsifiable. This RFC is the North Star foundation for Track Science.

## Detailed design

### Layout

```text
evaluation/
  README.md
  schema/place_label.schema.json
  fixtures/karakoram_mini/          # synthetic, CI-safe, Apache-2.0
    hidden_lakes.json
    forgotten_tracks.json
    controls.json
  skardu/                           # real curator labels (start empty / README)
  swat/
  gilgit/
  astore/
```

Each `*.json` file is a JSON array of **place labels** (schema below). Region directories group labels; filenames are thematic collections, not ontology.

### Place label schema (v0.1.0)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | string | yes | `"0.1.0"` |
| `id` | string | yes | Stable id, e.g. `fixtures/karakoram_mini/turquoise_lake` |
| `catalog_id` | string\|null | no | Pack catalog feature id when known |
| `geometry` | GeoJSON Point | yes | WGS84 |
| `known` | bool | yes | Whether place is generally known locally |
| `interesting` | bool | yes | Curator: worth an explorer's list |
| `human_rating` | float\|null | no | Prefer 0–10 scale when set |
| `google_maps_popularity` | float\|null | no | Optional 0–10 proxy; never fetched at score time |
| `tags` | string[] | no | Free tags (migrate toward ontology) |
| `ontology_ids` | string[] | no | e.g. `water.lake` (see ontology RFC) |
| `notes` | string\|null | no | Provenance of the rating |
| `license` | string | yes | SPDX or URL; per-record |
| `synthetic` | bool | yes | `true` for CI fixtures |

Matching ranked missions to labels:

1. Prefer exact `catalog_id` match when present on both sides.
2. Else nearest label within `match_radius_km` (default **2.0**) by haversine.

### Metrics (v0)

Computed offline by `scripts/eval_discovery.py` / `adventure_core.evaluation`:

| Metric | Definition |
|--------|------------|
| `recall_at_k` | Among labels with `interesting=true`, fraction matched in top-k ranked results |
| `precision_at_k` | Among top-k results that match any label, fraction with `interesting=true` |
| `popularity_trap_at_k` | Among top-k matched labels, fraction with `google_maps_popularity >= 7` (configurable) |
| `rating_spearman` | Spearman ρ between mission score and `human_rating` for matched pairs with ratings |

Primary North Star metric for the next stretch: **`recall_at_k` on `interesting=true`** (k=5 default), with popularity-trap as a guardrail. Formal freeze, metric map, and threats to validity: **RFC-0005**.

### Harness inputs

```bash
uv run python scripts/eval_discovery.py \
  --pack fixtures/karakoram_mini \
  --labels evaluation/fixtures/karakoram_mini \
  --prompt "…" \
  --interpreter rules \
  --k 5
```

Uses existing `run_mission` path — does not invent candidates.

### Licensing & ethics

- Synthetic fixture labels: Apache-2.0 with the code.
- Real labels: curator-authored; each record carries `license`; no scraping that violates ToS; no PII.
- Do not commit raw Google/API scrapes. Popularity scores are optional hand-entered proxies.
- Large real sets may later move to git-LFS or an external release; CI keeps the synthetic slice.

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators
- [ ] Pack manifest
- [x] CLI UX — optional script only (no MissionIntent change)
- [ ] None (docs/process only) — schema + harness are new surfaces under `adventure_core.evaluation`

## Alternatives considered

1. **Eval only via unit tests on fixtures** — insufficient for generator science.
2. **LLM-as-judge** — rejected as default; circular and non-local-first.
3. **Live popularity APIs in scoring** — rejected; eval-only optional fields, never score path.

## Reproducibility & attribution

Reports must include pack id / content hash when available, label directory path, schema version, k, match radius, and interpreter. OSM/DEM packs remain separately NOTICE'd; labels do not re-license basemap data.

## Migration / compatibility

Additive. `eval/golden_prompts.yaml` remains for intent regression. `evaluation/` is the place-label dataset.

## Unresolved questions

1. Exact N for first real Skardu set (propose ≥ 30 interesting + 15 controls).
2. Whether `ontology_ids` become required after the ontology RFC lands.
3. Whether reports publish under `evaluation/reports/` (gitignored) or `benchmarks/`.
