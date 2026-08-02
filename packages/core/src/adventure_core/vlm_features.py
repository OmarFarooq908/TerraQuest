"""Pack-time VLM feature records (RFC-0007 / issue #22).

Structured scene labels only — never ranking scores or invented coordinates.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from adventure_core.ontology import CONCEPT_TO_DIMENSIONS

VLM_FEATURES_VERSION = "vlm-features-v1"
DEFAULT_VLM_PROMPT_ID = "pack_vlm_v1"


class VlmFeatureRecord(BaseModel):
    """One catalog-point VLM label set (mission evidence; not a score)."""

    catalog_id: str
    vlm_version: str = VLM_FEATURES_VERSION
    model: str
    concept_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    prompt_id: str = DEFAULT_VLM_PROMPT_ID
    image_ref: str | None = None

    @field_validator("catalog_id", "model", "prompt_id", "vlm_version")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        text = str(v).strip()
        if not text:
            raise ValueError("must be a non-empty string")
        return text

    @field_validator("concept_ids")
    @classmethod
    def _concepts(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v:
            cid = str(item).strip()
            if cid and cid not in out:
                out.append(cid)
        return out


def annotate_unknown_concepts(record: VlmFeatureRecord) -> VlmFeatureRecord:
    """Flag concept_ids not in the transitional ontology map (do not drop)."""
    unknown = [c for c in record.concept_ids if c not in CONCEPT_TO_DIMENSIONS]
    attrs = dict(record.attributes)
    if unknown:
        attrs["unknown_concepts"] = unknown
    else:
        attrs.pop("unknown_concepts", None)
    return record.model_copy(update={"attributes": attrs})


def record_from_properties(props: dict[str, Any]) -> VlmFeatureRecord:
    """Validate a GeoJSON properties object into a VlmFeatureRecord."""
    raw = dict(props)
    if "vlm_version" not in raw and "version" in raw:
        raw["vlm_version"] = raw.pop("version")
    rec = VlmFeatureRecord.model_validate(raw)
    return annotate_unknown_concepts(rec)
