# Contributing to Adventure AI

Thanks for contributing. This project prioritizes **maintainability, determinism, and honest geospatial evidence** over feature velocity.

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [ROADMAP.md](ROADMAP.md).

## Architecture non-negotiables

1. **Deterministic GIS discovers** places (pack-time generators → catalog).
2. **LLMs only translate language → `MissionIntent`** (or narrate later). They never invent coordinates or pick winners.
3. **Mission engine = filter + score** over the catalog. No LLM-guided discovery.
4. **Synthetic fixtures** (`fixtures/`) are for CI/offline only. Production packs are OSM + DEM.

Breaking changes to `MissionIntent` or catalog schema require an [RFC](RFC/README.md).

## Development setup

```bash
# Python 3.12+
uv sync --group dev --group docs

# Optional: production pack builds
brew install osmium-tool   # macOS; see osmcode.org for other platforms
osmium --version

# Quality hooks
uv run pre-commit install

# Offline tests (no network)
uv run pytest
```

### Offline vs network work

| Task | Network? | Notes |
|------|----------|-------|
| `uv run pytest` | No | Uses `fixtures/karakoram_mini` |
| `adventurectl mission run --pack fixtures/...` | No | Rules interpreter |
| `adventurectl mission run --interpreter ollama` | Local Ollama | Optional |
| `adventurectl pack build --config skardu_v1` | Yes | Needs osmium + Geofabrik/DEM download |

## Project layout

- `packages/core` — schemas, `MissionIntent`, catalog types
- `packages/gis` — load catalog, featurize candidates
- `packages/scoring` — preference-vector ranking + confidence
- `packages/inference` — Ollama / rules router
- `packages/packbuilder` — OSM/DEM ingest + discovery generators
- `apps/cli` — `adventurectl`
- `configs/` — modes + pack build configs
- `fixtures/` — synthetic CI packs
- `docs/` — MkDocs site
- `RFC/` — design records

## Pull requests

1. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
2. Run `uv run pre-commit run --all-files` and `uv run pytest`.
3. Do not commit `data/packs/`, `data/cache/`, `.env`, or large binaries.
   Built Region Packs are local artifacts only ([RFC-0003](RFC/0003-region-pack-architecture.md)).
   PRs that add them will be rejected.
4. If you touch OSM/DEM handling, update attribution notes / pack `NOTICE` template as needed (ODbL / Copernicus).
5. New discovery generators need unit tests and docs under `docs/generators.md`.
6. Pack layout / hash / schema versioning changes need an [RFC](RFC/README.md) while we are in `0.x`.

## Coverage gates (P0)

CI enforces:

| Gate | Floor | Notes |
|------|------:|-------|
| Global (`adventure_core` + `gis` + `scoring`) | **70%** | `--cov-fail-under=70` |
| Per-module floors | see `configs/coverage_gates.yaml` | intent, polarity, catalog validate, scorers, pack load |

```bash
uv run pytest -q \
  --cov=adventure_core --cov=adventure_gis --cov=adventure_scoring \
  --cov-report=json:coverage.json --cov-fail-under=70
uv run python scripts/check_coverage_gates.py
```

Packbuilder / inference / CLI network paths are **out of** offline coverage requirements. Raise a floor in `configs/coverage_gates.yaml` when adding P0 correctness code — do not lower floors without an issue comment.

## Licensing

- Code: Apache-2.0 ([LICENSE](LICENSE))
- OpenStreetMap data: ODbL — share-alike obligations apply to OSM-derived pack redistribution
- Copernicus DEM: see pack `NOTICE` and upstream terms

By contributing, you agree that your contributions are licensed under Apache-2.0.
