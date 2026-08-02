"""Attach optional pack-time VLM feature layer (RFC-0007 / issue #22)."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

from adventure_core.config import repo_root
from adventure_core.pack_manifest import PackManifest, PackSource
from adventure_core.vlm_features import (
    DEFAULT_VLM_PROMPT_ID,
    VLM_FEATURES_VERSION,
    record_from_properties,
)
from pydantic import ValidationError

VLM_LAYER_NAME = "vlm_features.geojson"


class VlmBuildError(RuntimeError):
    """Misconfigured or incomplete VLM pack build options."""


def _as_enabled(val: Any) -> bool:
    """YAML-safe truthiness: ``\"false\"`` must not enable the hook."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return val != 0
    text = str(val).strip().lower()
    if text in {"", "0", "false", "no", "off", "disabled"}:
        return False
    return text in {"1", "true", "yes", "on", "enabled"}


def _validate_lon_lat(coords: Any, *, index: int) -> tuple[float, float]:
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        raise VlmBuildError(f"vlm features[{index}] coordinates must be [lon, lat]")
    try:
        lon = float(coords[0])
        lat = float(coords[1])
    except (TypeError, ValueError) as exc:
        raise VlmBuildError(f"vlm features[{index}] coordinates must be numeric") from exc
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise VlmBuildError(f"vlm features[{index}] coordinates must be finite")
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise VlmBuildError(f"vlm features[{index}] lon/lat out of WGS84 range")
    return lon, lat


def _normalize_vlm_fc(
    raw: dict[str, Any], *, default_model: str, default_prompt: str
) -> dict[str, Any]:
    if raw.get("type") != "FeatureCollection":
        raise VlmBuildError("vlm features GeoJSON must be a FeatureCollection")
    features = raw.get("features")
    if not isinstance(features, list):
        raise VlmBuildError("vlm features FeatureCollection missing features[]")
    if not features:
        raise VlmBuildError(
            "vlm features FeatureCollection is empty — disable vlm or provide labels"
        )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            raise VlmBuildError(f"vlm features[{i}] must be an object")
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            raise VlmBuildError(f"vlm features[{i}] must be Point geometry")
        lon, lat = _validate_lon_lat(geom.get("coordinates"), index=i)
        props = dict(feat.get("properties") or {})
        props.setdefault("model", default_model)
        props.setdefault("prompt_id", default_prompt)
        props.setdefault("vlm_version", VLM_FEATURES_VERSION)
        try:
            rec = record_from_properties(props)
        except (ValidationError, ValueError) as exc:
            raise VlmBuildError(f"vlm features[{i}] invalid: {exc}") from exc
        if rec.catalog_id in seen:
            raise VlmBuildError(
                f"vlm features duplicate catalog_id {rec.catalog_id!r} (must be 1:1 with catalog)"
            )
        seen.add(rec.catalog_id)
        out.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": rec.model_dump(mode="json"),
                **({"id": feat["id"]} if "id" in feat else {}),
            }
        )
    return {"type": "FeatureCollection", "features": out}


def clear_vlm_layer(layers_dir: Path) -> bool:
    path = layers_dir / VLM_LAYER_NAME
    if path.is_file():
        path.unlink()
        return True
    return False


def maybe_attach_vlm_features(
    config: PackManifest,
    layers_dir: Path,
) -> tuple[PackSource | None, bool]:
    """Attach precomputed VLM labels when ``vlm.enabled``.

    Live Ollama vision labeling is intentionally out of band for v1 — see RFC-0007.
    When disabled, leftover ``vlm_features.geojson`` is removed.
    """
    cfg = dict(config.vlm or {})
    if not _as_enabled(cfg.get("enabled")):
        clear_vlm_layer(layers_dir)
        return None, False

    raw_path = cfg.get("features_geojson")
    if not raw_path:
        raise VlmBuildError(
            "vlm.enabled is true but vlm.features_geojson is unset. "
            "Precompute a Point FeatureCollection (concept_ids per catalog_id) and "
            "point this path at it — see RFC-0007 / docs/pack-builder.md. "
            "Live Ollama vision inside pack build is not enabled yet."
        )

    src = Path(str(raw_path))
    if not src.is_absolute():
        src = repo_root() / src
    if not src.is_file():
        raise VlmBuildError(f"vlm.features_geojson not found: {src}")

    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VlmBuildError(f"vlm.features_geojson is not valid JSON: {src}") from exc
    if not isinstance(raw, dict):
        raise VlmBuildError("vlm features GeoJSON root must be an object")

    default_model = str(cfg.get("model") or "synthetic-precomputed")
    default_prompt = str(cfg.get("prompt_id") or DEFAULT_VLM_PROMPT_ID)
    normalized = _normalize_vlm_fc(raw, default_model=default_model, default_prompt=default_prompt)
    dest = layers_dir / VLM_LAYER_NAME
    dest.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")

    source = PackSource(
        kind="vlm",
        provider=str(cfg.get("provider") or f"pack-time VLM labels ({default_model})"),
        retrieved_at=cfg.get("retrieved_at"),
        license=str(cfg.get("license") or "Model output — see model card / Ollama license"),
        attribution=str(cfg.get("attribution") or "Local VLM pack-time labels (not a ranker)"),
        url=cfg.get("url"),
        content_hash=None,
        extra={
            "vlm_version": VLM_FEATURES_VERSION,
            "model": default_model,
            "prompt_id": default_prompt,
            "features_geojson": str(src),
            "feature_count": len(normalized["features"]),
            "role": "features_only_not_ranking",
        },
    )
    cache_hint = cfg.get("cache_copy")
    if cache_hint:
        cache_path = Path(str(cache_hint))
        if not cache_path.is_absolute():
            cache_path = repo_root() / cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, cache_path)
    return source, True
