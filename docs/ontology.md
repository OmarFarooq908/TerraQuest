# Adventure ontology

Shared vocabulary for concepts such as `water.lake` and `terrain.ridge`
([RFC-0008](https://github.com/OmarFarooq908/TerraQuest/blob/main/RFC/0008-formal-ontology.md)).

## Why it exists

Eval labels, catalog evidence, generators, and (later) VLM outputs need the
**same IDs**. Preference scoring still goes through `MissionIntent` —
the ontology only supplies concept → preference priors for interpreters.

## ID scheme

| Rule | Example |
|------|---------|
| Form | `family.concept` |
| Families (v1) | `water`, `terrain`, `vegetation`, `access`, `experience`, `risk` |
| Canonical | Always the dotted id |
| Aliases | Short legacy tokens (`lake`, `river`) for the rules interpreter |

Machine-readable source: [`configs/ontology/adventure_v1.yaml`](https://github.com/OmarFarooq908/TerraQuest/blob/main/configs/ontology/adventure_v1.yaml).

## Python API

```python
from adventure_core.ontology import (
    apply_concept,
    resolve_concept,
    validate_ontology_ids,
    water_kind_to_ontology_id,
)

resolve_concept("lake")           # → "water.lake"
apply_concept({}, "lake")         # preference nudges
validate_ontology_ids(["water.lake", "nope"])  # errors for unknown
```

`CONCEPT_TO_DIMENSIONS` remains available and is loaded from the YAML (canonical
ids **and** aliases).

## Catalog / generators

Water generators (`named_waterbody`, `unnamed_waterbody`) set:

```json
"evidence": {
  "ontology_ids": ["water.lake"],
  "...": "..."
}
```

Free-text `tags` stay transitional — prefer `ontology_ids` for new work.

## Eval labels

`PlaceLabel.ontology_ids` (RFC-0002) should use canonical dotted ids. CI checks
that fixture ids resolve against the ontology YAML.

## Migration notes

| Before | After |
|--------|-------|
| In-code `CONCEPT_TO_DIMENSIONS` only | YAML + loader; `apply_concept` unchanged |
| Undocumented dotted eval ids | Documented + CI-validated |
| Water evidence without ontology | Generators / fixture catalog emit `ontology_ids` |
