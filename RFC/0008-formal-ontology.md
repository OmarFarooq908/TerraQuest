# RFC-0008: Formal adventure ontology (shared language)

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/10

## Summary

Introduce a **versioned, machine-readable ontology** of adventure concepts
(`water.lake`, `terrain.ridge`, …) that VLM labels, generators, catalog evidence,
ranking bridges, and eval `ontology_ids` all share. Prefer stable IDs over free-text
tags. **MissionIntent remains the only bridge from language to scoring** — the
ontology informs interpreters/generators; it does not let an LLM invent rankings.

## Motivation

Today we have preference dimensions (`PREFERENCE_DIMENSIONS`) and a thin in-code
`CONCEPT_TO_DIMENSIONS` map. Eval fixtures already cite dotted IDs like
`water.lake`, but there is no single validated vocabulary. Without one, VLM
outputs (#22), generators, catalog tags, and labels drift apart.

## Detailed design

### 1. ID scheme

| Rule | Example |
|------|---------|
| Form | `family.concept` (lowercase, snake_case concept) |
| Families (v1) | `water`, `terrain`, `vegetation`, `access`, `experience`, `risk` |
| Canonical | Always the dotted id |
| Aliases | Short legacy tokens (`lake`, `river`) for rules interpreter only |

Breaking rename of a canonical id → bump `ontology_version` + RFC.

### 2. Artifact

`configs/ontology/adventure_v1.yaml`:

```yaml
ontology_version: "1.0.0"
id_scheme: family.concept
concepts:
  water.lake:
    label: Lake
    family: water
    aliases: [lake, lakes]
    preferences:
      water: 0.9
      beauty: 0.35
      photography: 0.2
```

Preference keys **must** be members of `PREFERENCE_DIMENSIONS`. Weights in `[-1, 1]`.

### 3. Python loader (`adventure_core.ontology`)

- Load YAML (cached); build:
  - `canonical_ids()`
  - `alias_to_canonical`
  - `CONCEPT_TO_DIMENSIONS` (canonical **and** aliases → same weights) for
    backward-compatible `apply_concept`
- `resolve_concept(token) -> canonical | None`
- `validate_ontology_ids(ids) -> errors`
- CI test: YAML parses; all preference keys valid; fixture `ontology_ids` ⊆ canonical

### 4. Relation to MissionIntent

| Layer | Role |
|-------|------|
| Ontology | Shared concept vocabulary + weak preference priors |
| Rules / LLM interpreter | Emit `MissionIntent` prefs/goals (may use aliases) |
| Scorer | Still ranks on preference vector + GIS features only |

Ontology does **not** replace `PREFERENCE_DIMENSIONS`. Mapping is one-way:
concept → preference nudges for interpreters.

### 5. Catalog / generators / VLM / eval

| Consumer | Contract |
|----------|----------|
| Generators | May set `evidence.ontology_ids: string[]` (canonical ids) |
| VLM layer (#22) | Prefer `concept_ids` that resolve to canonical ids |
| Eval labels | `ontology_ids[]` (RFC-0002); validate when present |
| Free-text `tags` | Transitional; do not invent new tag vocabularies |

### 6. Migration

| Before | After |
|--------|-------|
| In-code `CONCEPT_TO_DIMENSIONS` only | Loaded from YAML; code keeps `apply_concept` API |
| Eval dotted ids undocumented | Documented + CI-validated |
| Catalog water evidence without ontology | `named_waterbody` / `unnamed_waterbody` emit `ontology_ids` |

## Impact on contracts

- [ ] MissionIntent schema (unchanged)
- [x] Catalog evidence (additive `ontology_ids`)
- [ ] Pack manifest
- [ ] CLI UX
- [x] Docs (`docs/ontology.md`) + RFC-0008
- [x] Config artifact `configs/ontology/adventure_v1.yaml`

## Alternatives considered

1. **OWL / RDF stack** — too heavy for v1.
2. **Tags only** — already drifting; rejected.
3. **Fork preference dimensions per modality** — breaks MissionIntent bridge.

## Reproducibility & attribution

Ontology is project-authored (Apache-2.0). No third-party taxonomy required for v1.

## Unresolved questions

1. When to require `ontology_ids` on all catalog features (ledger v2).
2. Whether access concepts (`access.4x4`) should influence `vehicle_class` parsing.
3. Multi-lingual labels beyond English `label` fields.
