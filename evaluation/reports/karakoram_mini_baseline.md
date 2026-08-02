# Discovery ranking comparison

- pack: `karakoram_mini`
- pack_content_hash: `23405f3b9dafc17b`
- labels: `/Users/dev/Documents/Personal/open-source/AdventureAI/evaluation/fixtures/karakoram_mini`
- interpreter: `rules`
- mode: `fearless_far`
- k: `5`
- match_radius_km: `2.0`
- prompt: 'Three days, Suzuki Swift, rivers and forests, hate crowds. Find a Fearless & Far style adventure.'

Synthetic fixture-scale ablation (issue #24). Not a Skardu field study.
Filters rank among **existing catalog features** from selected generators
(post-catalog); they do not re-run packbuilder discovery.
Ablation `nDCG@k` uses a **pool-relative** ideal (labels whose `catalog_id`
is in the filtered catalog); `all_generators` uses the global ideal.

| Ablation | include_generators | recall@k | precision@k | nDCG@k | pop_trap@k | spearman | top ids |
|----------|--------------------|----------|-------------|--------|------------|----------|---------|
| all_generators | `(all)` | 0.5000 | 1.0000 | 0.4987 | 0.0000 | -0.5000 | `seed_pine_river`, `seed_river_ford`, `seed_shepherd_ruins` |
| water_only | `named_waterbody,unnamed_waterbody` | 0.3333 | 1.0000 | 0.7883 | 0.0000 | -1.0000 | `seed_pine_river`, `seed_river_ford`, `seed_turquoise_lake` |
| dem_terrain | `dem_local_max,terrain_relief_hotspot,isolation_maximum` | 0.5000 | 1.0000 | 0.8206 | 0.0000 | -0.5000 | `seed_shepherd_ruins`, `seed_silent_valley`, `seed_sunrise_ridge` |
| access_only | `track_terminus,road_spur` | 0.1667 | 1.0000 | — | 0.0000 | — | `seed_valley_spur`, `seed_forgotten_track` |
| osm_landmarks | `osm_peak,osm_viewpoint` | 0.0000 | — | — | — | — | `seed_granite_lookout`, `seed_needle_peak` |

## Notes

- North Star: maximize `recall_at_k` on `interesting=true` without inflating `popularity_trap_at_k`.
- `nDCG@k` uses label `human_rating` with exponential gain `(2^rel - 1) / log2(rank+1)`.
- Precision@k denominator is matched labels only; unlabeled tops do not dilute it.
- Re-run: `uv run python scripts/eval_discovery.py --ablations --write-report evaluation/reports/karakoram_mini_baseline.md`
