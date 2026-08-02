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

Primary North Star metric (RFC-0005 / issue #29): `recall_at_k` on `interesting=true`
(default k=5). Guardrail: `popularity_trap_at_k`. Pin: `configs/north_star.yaml`.
Also reported: `ndcg_at_k` (human_rating), `precision_at_k`, `rating_spearman`.

Threats to validity and offline metric map: `RFC/0005-measure-adventure.md`.

### Generator ablations

```bash
uv run python scripts/eval_discovery.py --ablations \
  --write-report evaluation/reports/karakoram_mini_baseline.md
```

Optional `--include-generators` / `--exclude-generators` filter catalog features before
ranking. Fixture baseline report: `reports/karakoram_mini_baseline.md` (pinned via
`pack_content_hash`).

## Adding real labels

1. Read RFC-0002 licensing rules (no ToS-violating scrapes; no PII).
2. Add `*.json` arrays under the region directory.
3. Set `synthetic: false` and a real `license` per record.
4. Prefer `ontology_ids` (canonical `family.concept` ids; see [RFC-0008](../RFC/0008-formal-ontology.md) and [docs/ontology.md](../docs/ontology.md)); `tags` are transitional.
