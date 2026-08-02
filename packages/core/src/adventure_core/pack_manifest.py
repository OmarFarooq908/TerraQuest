"""Region Pack manifest — production packs vs synthetic fixtures."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PackSource(BaseModel):
    kind: Literal["osm", "dem", "sentinel2", "synthetic"]
    provider: str
    retrieved_at: str | None = None
    license: str
    attribution: str
    url: str | None = None
    content_hash: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class PackManifest(BaseModel):
    pack_id: str
    name: str
    bbox: list[float]  # west, south, east, north
    crs: str = "EPSG:4326"
    feature_schema_version: str = "0.3.0"
    synthetic: bool = False
    sources: list[PackSource] = Field(default_factory=list)
    fixtures_dir: str | None = None
    output_dir: str | None = None
    built_at: str | None = None
    content_hash: str | None = None
    notes: str | None = None
    # Build config (present in configs/packs/*.yaml)
    osm: dict[str, Any] = Field(default_factory=dict)
    dem: dict[str, Any] = Field(default_factory=dict)
    discovery: dict[str, Any] = Field(default_factory=dict)
    # Deprecated: use discovery.generators quotas
    candidate_limits: dict[str, int] = Field(default_factory=dict)
