# Roadmap

Adventure AI / TerraQuest is in **`0.x`**: APIs and schemas may change with RFCs.

## North Star (current focus)

> Can we consistently discover places that an experienced explorer would genuinely add to their travel list?

Working balance: ~**80%** better data + evaluation, ~**20%** new features. Architecture for `MissionIntent` → deterministic GIS scoring stays frozen unless an RFC proves a North Star need.

**Primary metric (RFC-0005):** `recall_at_k` on `interesting=true` (k=5), guardrail `popularity_trap_at_k`. Pin: `configs/north_star.yaml`.

Milestone: **North Star — discovery quality** (see issues). Start here:

1. [#9 Evaluation dataset](https://github.com/OmarFarooq908/TerraQuest/issues/9) — provisional Skardu seed + corpus CI ([#56](https://github.com/OmarFarooq908/TerraQuest/issues/56)); grow toward field-verified counts
2. [#10 Formal ontology](https://github.com/OmarFarooq908/TerraQuest/issues/10)
3. [#29 Measuring “adventure”](https://github.com/OmarFarooq908/TerraQuest/issues/29) — RFC-0005
4. P0 correctness issues (intent, inversion, schema, confidence)

Project model (three tracks + P0–P4): [#8](https://github.com/OmarFarooq908/TerraQuest/issues/8).

## Near term — OSS foundation (0.2)

- [x] Deterministic discovery catalog (named generators)
- [x] Synthetic fixtures + offline golden missions
- [x] Community docs, CI quality gates, MkDocs
- [x] Canonical catalog contract (deprecate seeds dual-path)
- [x] Honest OSM backends (Geofabrik production; Overpass degraded)
- [x] Reproducible pack hashing + release workflow stubs

## Next — Reproducible packs (0.3)

- [x] Pinned Geofabrik dated extracts where practical (#60 — `skardu_v1` → `pakistan-260801`)
- Stronger content hashes across all layers
- Intent / schema regression suites (P0)
- Evidence ledger completeness
- [x] Region Pack architecture RFC

## Then — Public beta (0.4)

- Intent validation / repair for LLM interpreters
- Calibrated confidence (real vs synthetic packs)
- Documented known limits (haversine travel, party_size)
- Thin product UX (export/GPX) only where it helps field eval
  - [x] GPX waypoint export from `adventurectl mission run --export-gpx` (#58)

## Later (after North Star evidence)

- Real routing / access graphs (P2 — capability, not a bug)
- [ ] Sentinel-2 indices + VLM features (P1 — RFC-0006/0007 opt-in layers shipped; judged by eval lift)
- Mission-time local densification (Phase C) without changing `MissionIntent`
- Intelligence layer (explanations first; memory/KG later)
- PyPI publish of selected packages

## Out of scope for drive-by PRs

- Replacing the preference-vector scorer with an LLM ranker
- Calling external closed model APIs (OpenAI/Anthropic/Google) as defaults
- Committing built `data/packs/` or raw PBF/DEM tiles
- Filing missing future capabilities (routing, weather, map UI) as `bug`
