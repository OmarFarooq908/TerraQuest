# Local data directory (gitignored artifacts)

Built Region Packs and OSM/DEM caches live here and are **not** committed.
See [RFC-0003](../RFC/0003-region-pack-architecture.md) for the frozen pack contract.

| Path | Contents | How to create |
|------|----------|---------------|
| `data/cache/` | Geofabrik PBF downloads (~150MB+) | Created automatically by `adventurectl pack build` |
| `data/cache/sentinel2/` | Precomputed Sentinel-2 index GeoJSON for pack attach (RFC-0006) | Manual pilot / future STAC recipe |
| `data/cache/inference/` | Adventure-managed inference artifacts (future embeddings / VLM); not Ollama weights | Created on demand; override with `ADVENTURE_INFERENCE_CACHE` |
| `data/packs/<id>/` | Built packs (`pack.yaml`, `NOTICE`, `build_stats.json`, `layers/`, optional derived `query.duckdb`) | `uv run adventurectl pack build --config skardu_v1` then `pack materialize` |

Derived `query.duckdb` files are gitignored (`**/query.duckdb`) — never commit them (RFC-0004).

Ollama model weights live in Ollama’s own store (typically `~/.ollama`), not under `data/`.
See [docs/offline-inference.md](../docs/offline-inference.md).

For offline CI and contributor tests, use **`fixtures/karakoram_mini`** instead of this directory.

System dependency for production pack builds: [`osmium-tool`](https://osmcode.org/osmium-tool/) (`brew install osmium-tool`).

Validate a built pack (never commit it):

```bash
uv run python scripts/check_pack.py data/packs/skardu_v1
```
