# Eval delta note — Sentinel-2 indices (RFC-0006 / issue #21)

Date: 2026-08-02  
Pack: `fixtures/karakoram_mini` (synthetic) · `pack_content_hash: f7f6a397fd5fef00` (pack-content v2)  
Prompt: standard Fearless & Far / Swift / hate-crowds  
Interpreter: `rules` · mode: `fearless_far` · k=5

## Result

| Condition | `recall_at_k` | `popularity_trap_at_k` | Notes |
|-----------|---------------|------------------------|-------|
| GIS-only baseline (pre-layer hash `23693b81e85e7d2b`) | 0.5 | 0.0 | Prior pinned report |
| With synthetic `sentinel_indices` (`1aad7575ad0e7000`) | 0.5 | 0.0 | NDVI/NDWI on features; **ranking weights unchanged** |

Honesty: fixture lift is **zero by design** until preference blends are enabled
after a real Skardu pilot (RFC-0006 §7–8). Publish regional deltas there.
