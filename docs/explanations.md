# Ranking explanations

Deterministic **why this ranked** lines on each mission ([RFC-0009](https://github.com/OmarFarooq908/TerraQuest/blob/main/RFC/0009-ranking-explanations.md),
issue #27).

## What they are

`RankedMission.explanations` is a short list of `{code, detail}` derived from:

| Source | Code prefix |
|--------|-------------|
| Discovery-mode GIS prior | `mode.*` |
| Preference alignment | `pref.*` |
| Goals | `goal.*` |
| Travel / budget logistics | `constraint.*` |
| Catalog generator / ontology | `evidence.*` |

They are **not** confidence reasons (`confidence.reasons` = how sure).
They never change the score and never invent places.

Avoid-preferences (`human_activity=-0.9`) are explained with feature context
(“honors avoid-…”), not naïvely from the sign of `weight × feature`.

## CLI

```bash
uv run adventurectl mission "Hidden alpine lakes near Skardu" --pack fixtures/karakoram_mini
```

Human output includes a **Why these ranked** section. JSON includes `explanations`.

## API

```python
from adventure_scoring import build_ranking_explanations

reasons = build_ranking_explanations(
    feature_breakdown=...,
    preference_adjustments=...,
    evidence=...,
)
```

`rank_missions` attaches explanations automatically.
