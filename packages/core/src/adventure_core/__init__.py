"""Core schemas for Adventure AI missions, candidates, and confidence."""

from adventure_core.catalog import (
    CATALOG_SCHEMA_VERSION,
    CatalogCandidate,
    DensifyHook,
    DiscoveryConfig,
    Provenance,
)
from adventure_core.catalog_validate import (
    CatalogValidationError,
    validate_catalog_feature,
    validate_catalog_geojson,
)
from adventure_core.config import (
    ModeWeights,
    load_mode,
    load_pack_manifest,
    load_yaml,
    repo_root,
)
from adventure_core.constraints import MissionConstraints, parse_constraints
from adventure_core.evaluation import (
    PLACE_LABEL_SCHEMA_VERSION,
    DiscoveryMetrics,
    PlaceLabel,
    RankedRef,
    compute_discovery_metrics,
    load_place_labels,
)
from adventure_core.evidence_ledger import (
    EVIDENCE_LEDGER_VERSION,
    validate_evidence_ledger,
)
from adventure_core.geo import Point, haversine_km
from adventure_core.intent import (
    SCHEMA_VERSION,
    HardConstraints,
    IntentCoverage,
    MissionIntent,
    PreferenceVector,
)
from adventure_core.intent_validate import (
    IntentValidationError,
    sanitize_intent_dict,
    validate_and_repair_intent,
)
from adventure_core.interpreters import interpret_rules
from adventure_core.pack_manifest import PackManifest, PackSource
from adventure_core.polarity import (
    PolarityFinding,
    detect_preference_inversions,
    repair_preference_inversions,
)
from adventure_core.schemas import (
    Candidate,
    CandidateFeatures,
    Confidence,
    MissionRequest,
    MissionResult,
    RankedMission,
    ReasonCode,
)

__all__ = [
    "Point",
    "haversine_km",
    "Candidate",
    "CandidateFeatures",
    "Confidence",
    "MissionRequest",
    "MissionResult",
    "RankedMission",
    "ReasonCode",
    "MissionConstraints",
    "parse_constraints",
    "MissionIntent",
    "PreferenceVector",
    "HardConstraints",
    "IntentCoverage",
    "SCHEMA_VERSION",
    "interpret_rules",
    "CATALOG_SCHEMA_VERSION",
    "CatalogCandidate",
    "DensifyHook",
    "DiscoveryConfig",
    "Provenance",
    "CatalogValidationError",
    "validate_catalog_feature",
    "validate_catalog_geojson",
    "EVIDENCE_LEDGER_VERSION",
    "validate_evidence_ledger",
    "PackManifest",
    "PackSource",
    "ModeWeights",
    "load_mode",
    "load_pack_manifest",
    "load_yaml",
    "repo_root",
    "PLACE_LABEL_SCHEMA_VERSION",
    "PlaceLabel",
    "RankedRef",
    "DiscoveryMetrics",
    "load_place_labels",
    "compute_discovery_metrics",
    "PolarityFinding",
    "detect_preference_inversions",
    "repair_preference_inversions",
    "IntentValidationError",
    "sanitize_intent_dict",
    "validate_and_repair_intent",
]
