# Skardu evaluation labels

Curator-authored place labels for measuring discovery quality around Skardu
(RFC-0002 / issues #9, #56).

## Status

**Provisional seed (v0)** — public geography with curator ratings marked in `notes`
as pending field verification. Not a claim of exhaustive local knowledge.
**Do not** quote North Star product claims from this seed alone.

| File | Role |
|------|------|
| `hidden_lakes.json` | Interesting waterbodies |
| `forgotten_tracks.json` | Quiet valleys / tracks / plateau points |
| `controls.json` | High-popularity / tourist-circuit traps |

Counts (v0): **12** `interesting=true`, **5** controls (`interesting=false` and
`google_maps_popularity ≥ 7`). North Star stretch target remains **≥ 30** interesting
+ **≥ 15** controls.

All records: `synthetic: false`, `license: CC-BY-4.0`.

### Matching / density note

Offline matching uses exact `catalog_id` when present, else haversine ≤
`match_radius_km` (default 2 km). Opposite-interesting labels closer than
**2× match radius** are rejected by CI (`validate_place_label_corpus`) because a
midpoint candidate can flip polarity (false recall / missed popularity trap).

That is why **Shangrila / Lower Kachura is not included** as a control opposite
Upper Kachura — real geography is too tight. Prefer far tourist traps, or wait
for pack `catalog_id` links.

## Metrics note

`scripts/eval_discovery.py` needs a Region Pack whose catalog covers these
coordinates. The CI smoke pack (`fixtures/karakoram_mini`) does **not** cover Skardu;
keep using `evaluation/fixtures/karakoram_mini` for CI recall. Run Skardu metrics
when you have a Skardu (or wider Baltistan) pack:

```bash
uv run python scripts/eval_discovery.py \
  --pack /path/to/skardu_pack \
  --labels evaluation/skardu \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds." \
  --k 5
```

## Extending

1. Append objects to the thematic JSON arrays (or add a new `*.json` array).
2. Keep `schema_version: "0.1.0"` and unique `id`s like `skardu/<theme>/<slug>`.
3. Prefer canonical `ontology_ids` from `configs/ontology/adventure_v1.yaml`.
4. Keep opposite-interesting pairs **> 4 km** apart (2× default match radius).
5. Run `uv run pytest -q tests/test_evaluation_labels.py`.

See `../README.md` and `RFC/0002-evaluation-dataset.md`.
