"""Pack-time VLM feature records (RFC-0007 / issue #22).

Structured scene labels only — never ranking scores or invented coordinates.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from adventure_core.ontology import CONCEPT_TO_DIMENSIONS

VLM_FEATURES_VERSION = "vlm-features-v1"
DEFAULT_VLM_PROMPT_ID = "pack_vlm_v1"

# Top-level property keys that would violate the hard rule (VLM must not rank).
FORBIDDEN_RANKING_KEYS = frozenset(
    {
        "score",
        "rank",
        "ranking",
        "mission_score",
        "ranking_score",
        "best_mission",
        "winner",
        "preference_score",
    }
)


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

    @field_validator("vlm_version")
    @classmethod
    def _known_version(cls, v: str) -> str:
        if v != VLM_FEATURES_VERSION:
            raise ValueError(f"unsupported vlm_version {v!r}; expected {VLM_FEATURES_VERSION!r}")
        return v

    @field_validator("concept_ids")
    @classmethod
    def _concepts(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v:
            cid = str(item).strip()
            if cid and cid not in out:
                out.append(cid)
        return out


def assert_no_ranking_keys(props: dict[str, Any], *, where: str = "properties") -> None:
    """Fail closed if a record smuggles ranking fields (RFC-0007 hard rule)."""
    bad = sorted(k for k in props if str(k).lower() in FORBIDDEN_RANKING_KEYS)
    if bad:
        raise ValueError(f"{where} must not include ranking keys {bad} (VLM is not a ranker)")
    attrs = props.get("attributes")
    if isinstance(attrs, dict):
        bad_attrs = sorted(k for k in attrs if str(k).lower() in FORBIDDEN_RANKING_KEYS)
        if bad_attrs:
            raise ValueError(
                f"attributes must not include ranking keys {bad_attrs} (VLM is not a ranker)"
            )


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
    assert_no_ranking_keys(raw)
    if "vlm_version" not in raw and "version" in raw:
        raw["vlm_version"] = raw.pop("version")
    rec = VlmFeatureRecord.model_validate(raw)
    return annotate_unknown_concepts(rec)
