# Discovery ranking comparison

- pack: `karakoram_mini`
- pack_content_hash: `23693b81e85e7d2b`
- interpreter: `rules`
- mode: `fearless_far`
- k: `5`
- prompt: 'Three days, Suzuki Swift, rivers and forests, hate crowds. Find a Fearless & Far style adventure.'

Synthetic fixture-scale ablation (issue #24). Not a Skardu field study.

| Ablation | include_generators | recall@k | precision@k | nDCG@k | pop_trap@k | spearman | top ids |
|----------|--------------------|----------|-------------|--------|------------|----------|---------|
| all_generators | `(all)` | 0.5000 | 1.0000 | 0.4987 | 0.0000 | -0.5000 | `seed_pine_river`, `seed_river_ford`, `seed_shepherd_ruins` |
| water_only | `named_waterbody,unnamed_waterbody` | 0.3333 | 1.0000 | 0.4626 | 0.0000 | -1.0000 | `seed_pine_river`, `seed_river_ford`, `seed_turquoise_lake` |
| dem_terrain | `dem_local_max,terrain_relief_hotspot,isolation_maximum` | 0.5000 | 1.0000 | 0.4501 | 0.0000 | -0.5000 | `seed_shepherd_ruins`, `seed_silent_valley`, `seed_sunrise_ridge` |
| access_only | `track_terminus,road_spur` | 0.1667 | 1.0000 | 0.2059 | 0.0000 | — | `seed_valley_spur`, `seed_forgotten_track` |

## Notes

- North Star: maximize `recall_at_k` on `interesting=true` without inflating `popularity_trap_at_k`.
- `nDCG@k` uses label `human_rating` as graded relevance.
- Re-run: `uv run python scripts/eval_discovery.py --ablations --write-report evaluation/reports/karakoram_mini_baseline.md`
