"""Pinned local runtimes/models from ``configs/models.yaml`` — no cloud APIs."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from adventure_core.config import configs_dir, load_yaml
from pydantic import BaseModel, Field

DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2"
DEFAULT_FALLBACKS = ("llama3.2", "llama3.1:8b", "qwen3:8b", "llama3.2:3b")


class HardwareFloor(BaseModel):
    ram_gb: float = 4.0
    notes: str = ""


class ModelsConfig(BaseModel):
    runtime: str = "ollama"
    default_base_url: str = DEFAULT_OLLAMA_BASE
    default_model: str = DEFAULT_MODEL
    mission_interpreter: str = DEFAULT_MODEL
    pack_vlm: str = "llava"
    fallback: list[str] = Field(default_factory=lambda: list(DEFAULT_FALLBACKS))
    hardware_floors: dict[str, HardwareFloor] = Field(default_factory=dict)
    cache_inference_dir: str = "data/cache/inference"


def ollama_base_url(override: str | None = None) -> str:
    """Resolve Ollama HTTP base URL (env beats config; no cloud endpoints)."""
    if override:
        return _normalize_base(override)
    env = (
        os.environ.get("ADVENTURE_OLLAMA_BASE_URL", "").strip()
        or os.environ.get("OLLAMA_HOST", "").strip()
    )
    if env:
        return _normalize_base(env)
    return _normalize_base(load_models_config().default_base_url)


def _normalize_base(host: str) -> str:
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return host


@lru_cache(maxsize=1)
def load_models_config() -> ModelsConfig:
    path = configs_dir() / "models.yaml"
    if not path.is_file():
        return ModelsConfig()
    raw: dict[str, Any] = load_yaml(path)
    floors_raw = raw.get("hardware_floors") or {}
    floors = {
        str(k): HardwareFloor.model_validate(v if isinstance(v, dict) else {"ram_gb": v})
        for k, v in floors_raw.items()
    }
    cache = raw.get("cache") or {}
    inference_dir = cache.get("inference_dir") or raw.get("cache_inference_dir")
    return ModelsConfig(
        runtime=str(raw.get("runtime") or "ollama"),
        default_base_url=str(raw.get("default_base_url") or DEFAULT_OLLAMA_BASE),
        default_model=str(raw.get("default_model") or DEFAULT_MODEL),
        mission_interpreter=str(
            raw.get("mission_interpreter") or raw.get("default_model") or DEFAULT_MODEL
        ),
        pack_vlm=str(raw.get("pack_vlm") or "llava"),
        fallback=[str(x) for x in (raw.get("fallback") or list(DEFAULT_FALLBACKS))],
        hardware_floors=floors,
        cache_inference_dir=str(inference_dir or "data/cache/inference"),
    )


def clear_models_config_cache() -> None:
    load_models_config.cache_clear()
