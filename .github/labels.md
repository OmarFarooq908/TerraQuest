# Labels

Create via `gh label` or GitHub UI. Live labels should match this table.

## Tracks (parallel workstreams)

| Label | Use |
|-------|-----|
| `track:research` | What makes this not “another AI app” (packs, generators, sensors, offline inference) |
| `track:product` | Would someone actually use this? (UX, export, caching, search) |
| `track:science` | Measurable experiments / papers (eval datasets, bakeoffs, metrics) |

## Priority lanes

| Label | Use |
|-------|-----|
| `priority:p0` | Correctness — trustworthy recommendations |
| `priority:p1` | Discovery — packs, generators, catalog, sensors |
| `priority:p2` | Access — routing, fuel, weather (**capabilities**, not bugs) |
| `priority:p3` | Intelligence — explanations, embeddings, memory, KG |
| `priority:p4` | UX — map, export, GPX, offline, sharing |

## Type / domain

| Label | Use |
|-------|-----|
| `bug` | Defects in current behavior (e.g. bad remoteness sentinels) — **not** missing future features |
| `enhancement` | New feature or request |
| `correctness` | Trust / validation / regression |
| `epic` | Parent spanning multiple work items |
| `research` | Research / eval / experiments |
| `pack` | Region Pack requests or pack-builder work |
| `generator` | Discovery generator work |
| `good first issue` | New contributor friendly |
| `breaking-change` | Requires RFC / minor bump |
| `needs-rfc` | Blocked on design record in `RFC/` |
| `documentation` | Docs only |
| `ci` | CI / tooling / workflows |
| `dependencies` | Dependency updates |
| `github_actions` | GitHub Actions updates |

## Triage rule of thumb

- Missing routing / weather → `priority:p2` + `enhancement` (not `bug`)
- Wrong intent sign / illegal feature value → `priority:p0` + `bug` / `correctness`
- “Is generator A better?” → `track:science` + eval dataset work
