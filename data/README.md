# Local data directory (gitignored artifacts)

Built Region Packs and OSM/DEM caches live here and are **not** committed.

| Path | Contents | How to create |
|------|----------|---------------|
| `data/cache/` | Geofabrik PBF downloads (~150MB+) | Created automatically by `adventurectl pack build` |
| `data/cache/inference/` | Adventure-managed inference artifacts (future embeddings / VLM); not Ollama weights | Created on demand; override with `ADVENTURE_INFERENCE_CACHE` |
| `data/packs/<id>/` | Built packs (catalog, layers, NOTICE) | `uv run adventurectl pack build --config skardu_v1` |

Ollama model weights live in Ollama’s own store (typically `~/.ollama`), not under `data/`.
See [docs/offline-inference.md](../docs/offline-inference.md).

For offline CI and contributor tests, use **`fixtures/karakoram_mini`** instead of this directory.

System dependency for production pack builds: [`osmium-tool`](https://osmcode.org/osmium-tool/) (`brew install osmium-tool`).
