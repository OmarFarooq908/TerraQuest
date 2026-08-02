# Evaluation datasets

Human- and curator-rated places for measuring **discovery quality** (RFC-0002).

This is **not** the same as `eval/golden_prompts.yaml` (intent regression).

## Layout

| Path | Purpose |
|------|---------|
| `schema/place_label.schema.json` | JSON Schema for a place label |
| `fixtures/karakoram_mini/` | Synthetic labels aligned to the offline fixture pack (CI) |
| `skardu/`, `swat/`, `gilgit/`, `astore/` | Real regional labels (curator-authored; start with README) |

## Run metrics

```bash
uv run python scripts/eval_discovery.py \
  --pack fixtures/karakoram_mini \
  --labels evaluation/fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds." \
  --k 5
```

Primary North Star metric: `recall_at_k` on `interesting=true` (see RFC-0002).

## Adding real labels

1. Read RFC-0002 licensing rules (no ToS-violating scrapes; no PII).
2. Add `*.json` arrays under the region directory.
3. Set `synthetic: false` and a real `license` per record.
4. Prefer `ontology_ids` once the ontology RFC lands; `tags` are transitional.
