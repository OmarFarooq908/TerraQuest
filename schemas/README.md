# Schema pins

Checked-in JSON Schemas for core contracts (Roadmap 0.3 / issue #66):

| File | Contract |
|------|----------|
| [`schemas/mission_intent.schema.json`](../schemas/mission_intent.schema.json) | `MissionIntent` 1.0 + preference dimensions |
| [`schemas/catalog_feature.schema.json`](../schemas/catalog_feature.schema.json) | Catalog Feature properties 0.3.0 |
| [`evaluation/schema/place_label.schema.json`](../evaluation/schema/place_label.schema.json) | Place labels (RFC-0002) |

`tests/test_schema_regression.py` fails CI if preference dimensions, hard-constraint
fields, or required catalog keys drift from the live Pydantic models without
updating these pins.

When intentionally changing a contract: bump `SCHEMA_VERSION` /
`CATALOG_SCHEMA_VERSION` (via RFC when breaking), update the pin file, and adjust
tests/docs in the same PR.
