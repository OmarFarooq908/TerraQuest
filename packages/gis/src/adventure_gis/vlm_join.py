"""Join optional pack-time VLM labels onto candidates (RFC-0007 / issue #22)."""

from __future__ import annotations

from typing import Any

from adventure_core.vlm_features import VlmFeatureRecord, record_from_properties
from pydantic import ValidationError

from adventure_gis.pack_data import NamedPoint


def lookup_vlm_features(
    catalog_id: str,
    features: list[NamedPoint],
) -> dict[str, Any] | None:
    """Exact ``catalog_id`` join only — never invent or distance-steal labels."""
    if not features:
        return None
    for pt in features:
        cid = pt.properties.get("catalog_id")
        if cid is None or str(cid) != catalog_id:
            continue
        try:
            rec: VlmFeatureRecord = record_from_properties(
                {**pt.properties, "catalog_id": catalog_id}
            )
        except ValidationError:
            return None
        return rec.model_dump(mode="json")
    return None
