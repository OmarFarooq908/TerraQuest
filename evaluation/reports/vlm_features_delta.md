# Eval delta note — pack-time VLM features (RFC-0007 / issue #22)

Date: 2026-08-02  
Pack: `fixtures/karakoram_mini` (synthetic) · `pack_content_hash: 8e68daaa09771542`  
Prompt: standard Fearless & Far / Swift / hate-crowds  
Interpreter: `rules` · mode: `fearless_far` · k=5

## Result

| Condition | `recall_at_k` | `popularity_trap_at_k` | Notes |
|-----------|---------------|------------------------|-------|
| GIS-only baseline (pre-VLM layer) | 0.5 | 0.0 | Prior pinned report |
| With synthetic `vlm_features` | 0.5 | 0.0 | Labels in `evidence.vlm`; **ranking weights unchanged** |

Honesty: fixture lift is **zero by design** until preference blends are enabled
after a real regional bakeoff (RFC-0007). Hard rule: VLM is never the ranker.
