# Schema pins

Checked-in JSON Schemas for core contracts (Roadmap 0.3 / issue #66):

| File | Contract |
|------|----------|
| [`mission_intent.schema.json`](mission_intent.schema.json) | `MissionIntent` 1.0 + preference dimensions + known goals / vehicle classes |
| [`catalog_feature.schema.json`](catalog_feature.schema.json) | Catalog Feature properties 0.3.0 |
| [`../evaluation/schema/place_label.schema.json`](../evaluation/schema/place_label.schema.json) | Place labels (RFC-0002) |

`tests/test_schema_regression.py` fails CI if preference dimensions, hard-constraint
fields, known goals/vehicle classes, or catalog keys drift from the live Pydantic /
`intent_validate` constants without updating these pins.

Pins describe the **post-sanitize** shape (defaults filled, unknown goals dropped).
Top-level and nested objects set `additionalProperties: false`.

When intentionally changing a contract: bump `SCHEMA_VERSION` /
`CATALOG_SCHEMA_VERSION` (via RFC when breaking), update the pin file, and adjust
tests/docs in the same PR.
