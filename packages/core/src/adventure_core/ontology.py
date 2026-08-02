"""Formal adventure ontology — versioned concepts + preference priors.

Canonical ids use ``family.concept`` (RFC-0008). Legacy short tokens remain
resolvable for the rules interpreter via aliases. MissionIntent is still the
only bridge from language to scoring; this module does not invent rankings.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from adventure_core.config import configs_dir, load_yaml, repo_root
from adventure_core.intent import PREFERENCE_DIMENSIONS

DEFAULT_ONTOLOGY_REL = Path("configs") / "ontology" / "adventure_v1.yaml"
_FAMILIES = frozenset({"water", "terrain", "vegetation", "access", "experience", "risk"})


@dataclass(frozen=True)
class ConceptDef:
    id: str
    label: str
    family: str
    aliases: tuple[str, ...]
    preferences: dict[str, float]


@dataclass(frozen=True)
class AdventureOntology:
    version: str
    id_scheme: str
    concepts: dict[str, ConceptDef]
    alias_to_canonical: dict[str, str]
    #: Canonical id **and** each alias → preference weights (interpreter bridge).
    concept_to_dimensions: dict[str, dict[str, float]]

    def resolve(self, token: str) -> str | None:
        """Return canonical id for a dotted id or legacy alias, else None."""
        t = token.strip()
        if not t:
            return None
        if t in self.concepts:
            return t
        return self.alias_to_canonical.get(t)

    def canonical_ids(self) -> frozenset[str]:
        return frozenset(self.concepts)


def validate_ontology_data(data: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors (empty ⇒ ok)."""
    errors: list[str] = []
    version = data.get("ontology_version")
    if not isinstance(version, str) or not version.strip():
        errors.append("ontology_version must be a non-empty string")

    concepts = data.get("concepts")
    if not isinstance(concepts, dict) or not concepts:
        errors.append("concepts must be a non-empty mapping")
        return errors

    seen_aliases: dict[str, str] = {}
    for cid, raw in concepts.items():
        if not isinstance(cid, str) or "." not in cid:
            errors.append(f"concept id must be family.concept, got {cid!r}")
            continue
        family, _, concept = cid.partition(".")
        if not family or not concept or "." in concept:
            errors.append(f"concept id must be exactly one dot: {cid!r}")
            continue
        if family not in _FAMILIES:
            errors.append(f"{cid}: unknown family {family!r} (allowed: {sorted(_FAMILIES)})")
        if not isinstance(raw, dict):
            errors.append(f"{cid}: concept body must be a mapping")
            continue
        if raw.get("family") != family:
            errors.append(f"{cid}: family field {raw.get('family')!r} must match id prefix")
        label = raw.get("label")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{cid}: label must be a non-empty string")
        aliases = raw.get("aliases", [])
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            errors.append(f"{cid}: aliases must be a list of strings")
            aliases = []
        for alias in aliases:
            a = alias.strip()
            if not a:
                errors.append(f"{cid}: empty alias")
                continue
            if a in concepts:
                errors.append(f"{cid}: alias {a!r} collides with a canonical id")
            if a in seen_aliases and seen_aliases[a] != cid:
                errors.append(f"alias {a!r} claimed by both {seen_aliases[a]!r} and {cid!r}")
            else:
                seen_aliases[a] = cid
        prefs = raw.get("preferences", {})
        if not isinstance(prefs, dict):
            errors.append(f"{cid}: preferences must be a mapping")
            continue
        if not prefs:
            errors.append(f"{cid}: preferences must be non-empty")
        for dim, weight in prefs.items():
            if dim not in PREFERENCE_DIMENSIONS:
                errors.append(f"{cid}: preference key {dim!r} not in PREFERENCE_DIMENSIONS")
            try:
                w = float(weight)
            except (TypeError, ValueError):
                errors.append(f"{cid}: weight for {dim!r} must be numeric")
                continue
            if w < -1.0 or w > 1.0:
                errors.append(f"{cid}: weight for {dim!r} must be in [-1, 1], got {w}")
    return errors


def _build_ontology(data: dict[str, Any], *, source: Path | str) -> AdventureOntology:
    errs = validate_ontology_data(data)
    if errs:
        joined = "; ".join(errs)
        raise ValueError(f"Invalid ontology ({source}): {joined}")

    concepts: dict[str, ConceptDef] = {}
    alias_to_canonical: dict[str, str] = {}
    concept_to_dimensions: dict[str, dict[str, float]] = {}

    for cid, raw in data["concepts"].items():
        aliases = tuple(str(a).strip() for a in (raw.get("aliases") or []) if str(a).strip())
        prefs = {str(k): float(v) for k, v in raw["preferences"].items()}
        cdef = ConceptDef(
            id=cid,
            label=str(raw["label"]),
            family=str(raw["family"]),
            aliases=aliases,
            preferences=prefs,
        )
        concepts[cid] = cdef
        concept_to_dimensions[cid] = dict(prefs)
        for alias in aliases:
            alias_to_canonical[alias] = cid
            concept_to_dimensions[alias] = dict(prefs)

    return AdventureOntology(
        version=str(data["ontology_version"]),
        id_scheme=str(data.get("id_scheme") or "family.concept"),
        concepts=concepts,
        alias_to_canonical=alias_to_canonical,
        concept_to_dimensions=concept_to_dimensions,
    )


def _resolve_ontology_path(path: str | Path | None) -> Path:
    if path is None:
        return repo_root() / DEFAULT_ONTOLOGY_REL
    p = Path(path)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == "configs":
        return repo_root() / p
    # Relative to configs/ (e.g. ontology/adventure_v1.yaml)
    return configs_dir() / p


@lru_cache(maxsize=4)
def load_ontology(path: str | None = None) -> AdventureOntology:
    """Load and cache the ontology YAML.

    ``path`` may be absolute, repo-relative (``configs/ontology/...``), or
    relative to ``configs/`` (``ontology/adventure_v1.yaml``).
    """
    p = _resolve_ontology_path(path)
    data = load_yaml(p)
    return _build_ontology(data, source=p)


def reload_ontology(path: str | None = None) -> AdventureOntology:
    """Clear cache and reload (tests / tooling)."""
    load_ontology.cache_clear()
    ont = load_ontology(path)
    _sync_compat(ont)
    return ont


def get_ontology() -> AdventureOntology:
    return load_ontology()


def resolve_concept(token: str) -> str | None:
    return get_ontology().resolve(token)


def validate_ontology_ids(ids: Iterable[str]) -> list[str]:
    """Return errors for unknown ontology ids (aliases accepted → no error)."""
    ont = get_ontology()
    errors: list[str] = []
    for raw in ids:
        if not isinstance(raw, str) or not raw.strip():
            errors.append(f"invalid ontology id: {raw!r}")
            continue
        if ont.resolve(raw) is None:
            errors.append(f"unknown ontology id: {raw!r}")
    return errors


def apply_concept(
    prefs: dict[str, float],
    concept: str,
    *,
    strength: float = 1.0,
    invert: bool = False,
) -> dict[str, float]:
    """Merge a concept (canonical or alias) into a preference dict. strength in [0, 1]."""
    dims = CONCEPT_TO_DIMENSIONS.get(concept)
    if not dims:
        dims = get_ontology().concept_to_dimensions.get(concept)
    if not dims:
        return prefs
    sign = -1.0 if invert else 1.0
    out = dict(prefs)
    for dim, w in dims.items():
        delta = sign * float(w) * max(0.0, min(1.0, strength))
        out[dim] = max(-1.0, min(1.0, out.get(dim, 0.0) + delta))
    return out


def water_kind_to_ontology_id(kind: str) -> str:
    """Map generator ``water_kind`` values to canonical ontology ids."""
    k = (kind or "lake").strip().lower()
    mapping = {
        "lake": "water.lake",
        "river": "water.river",
        "tarn": "water.tarn",
        "glacier": "water.glacier",
        "waterfall": "water.waterfall",
        "falls": "water.waterfall",
    }
    return mapping.get(k, "water.body")


def _sync_compat(ont: AdventureOntology) -> None:
    global CONCEPT_TO_DIMENSIONS
    CONCEPT_TO_DIMENSIONS = dict(ont.concept_to_dimensions)


# Backward-compatible module-level map (canonical + aliases), populated on import.
CONCEPT_TO_DIMENSIONS: dict[str, dict[str, float]] = {}
try:
    _sync_compat(load_ontology())
except Exception:  # pragma: no cover - allow import when configs missing in odd envs
    CONCEPT_TO_DIMENSIONS = {}
