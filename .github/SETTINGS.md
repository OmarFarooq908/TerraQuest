# GitHub repository settings (live checklist)

Applied against [OmarFarooq908/TerraQuest](https://github.com/OmarFarooq908/TerraQuest). Re-check after recreating the remote.

## About

| Setting | Value |
|---------|--------|
| Description | Local-first exploration intelligence: missions, not itineraries. … |
| Homepage | `docs/` tree on `main` (swap to Pages URL when published) |
| Topics | `python`, `gis`, `openstreetmap`, `osm`, `dem`, `local-first`, `offline`, `exploration`, `geofabrik`, `copernicus`, `adventure`, `mission-planning` |
| Wiki | Off (docs live in-repo / MkDocs) |
| Discussions | On |
| Issues / Projects | On |
| Delete branch on merge | On |
| Merge style | Squash + rebase; merge commits off (linear history) |
| Default squash message | PR title + description |

## Security

- Private vulnerability reporting: on
- Dependabot alerts + security updates: on
- Secret scanning + push protection: on (GitHub default for public)

## Branch protection (`main`)

- Required checks: `lint-test (3.12)`, `lint-test (3.13)`, `docs`
- Require branches up to date before merge
- Require linear history
- Disallow force pushes and branch deletion
- Approving reviews: not required yet (solo maintainer); enable when collaborators join
- `enforce_admins`: off so the owner can emergency-bypass

## Labels

See [`labels.md`](labels.md). Custom labels created: `research`, `pack`, `generator`, `breaking-change`, `needs-rfc`, `ci`.

## Milestones

1. `0.2 OSS foundation` (closed)
2. `0.3 Reproducible packs` (open)
3. `0.4 Public beta` (open)

## Discussions categories

Defaults after enable: Announcements, General, Ideas, Polls, Q&A, Show and tell.

Suggested renames in **Settings → General → Discussions** (API cannot edit categories yet):

| Category | Purpose |
|----------|---------|
| Q&A | Usage and setup help |
| Show and tell | Missions, packs, experiments |
| Ideas → Pack ideas | Soft proposals before a Pack request issue |
| Add **RFCs** | Design discussion before / alongside `RFC/` PRs |
| Polls | Optional; hide if unused |

Welcome post: [Discussions #8](https://github.com/OmarFarooq908/TerraQuest/discussions/8).
