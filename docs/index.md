# Adventure AI docs

Local-first exploration intelligence: **deterministic GIS discovers** places; LLMs only interpret language into [`MissionIntent`](mission-intent.md). Models never invent coordinates or pick winners.

## Start here

| Path | When |
|------|------|
| [CLI](cli.md) | Run `adventurectl` offline or on a real pack |
| [Development](development.md) | Set up uv, hooks, quality gates |
| [Pack builder](pack-builder.md) | Build Skardu-class packs (needs osmium + network) |
| [Architecture](architecture.md) | Non-negotiables and package map |
| [Known limits](known-limits.md) | What not to “fix” with drive-by PRs |

Offline smoke (from the repo root — note `--pack` must be the fixture; the CLI
default is `skardu_v1`):

```bash
uv sync --group dev
uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds."
```

## Reference

- [MissionIntent](mission-intent.md)
- [Generators](generators.md)
- [GIS features](gis-features.md)
- [Evaluation](evaluation.md)
- [Confidence](confidence.md)
- [Offline inference](offline-inference.md)

```bash
uv sync --group docs
uv run mkdocs serve
```
