# MissionIntent specification (schema 1.0)

`MissionIntent` is the only bridge from language to scoring. Interpreters must not emit rankings.

## Fields

| Field | Role |
|-------|------|
| `schema_version` | `"1.0"` |
| `source` | `rules` \| `llm` \| `hybrid` |
| `constraints` | Hard logistics (`HardConstraints`) |
| `preferences` | `PreferenceVector` in `[-1, 1]` per dimension |
| `goals` | Soft goal ids |
| `interpreter_notes` | Provenance / fallback notes |

## Preference dimensions

See `PREFERENCE_DIMENSIONS` in `adventure_core.intent` (beauty, water, remoteness, forest, human_activity, …).

- Positive → seek
- Negative → avoid
- `0` → unspecified

## Hard constraints

`vehicle`, `vehicle_class`, `days`, `origin`, `budget_per_person`, `party_size`, …

Travel estimates currently use haversine / 45 km/h (not a real router) — see [known limits](known-limits.md).

## Mode priors

`merge_mode_prior(mode_id)` blends discovery-mode YAML weights into the preference vector without erasing explicit user signal.
