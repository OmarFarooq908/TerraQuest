# Known limits

Documented so contributors do not “fix” them with architecture-breaking PRs.

| Limit | Status |
|-------|--------|
| Travel time | Haversine / 45 km/h heuristic — not a road router |
| `party_size` | Parsed; camping capacity not scored |
| Confidence | Heuristic noisy-OR; not empirically calibrated |
| Overpass ingest | Degraded (no road_lines); opt-in only |
| LLM intent | May invert preferences; use `--interpreter rules` for CI |
| Sentinel-2 | Not in v1 packs |
| Mission-time densify | Schema hooks only (Phase C later) |

Propose changes via an RFC under the repository `RFC/` directory (see `RFC/README.md`).
