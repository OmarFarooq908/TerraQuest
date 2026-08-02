"""Gitignored cache layout for Adventure-managed inference artifacts.

Ollama model weights live in Ollama's own store (typically ``~/.ollama``), not
in the repo. This package only manages *our* caches under ``data/cache/``.
"""

from __future__ import annotations

import os
from pathlib import Path

from adventure_core.config import repo_root


def inference_cache_dir(*, create: bool = False) -> Path:
    """Return ``data/cache/inference`` (or ``ADVENTURE_INFERENCE_CACHE`` override)."""
    override = os.environ.get("ADVENTURE_INFERENCE_CACHE", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        path = repo_root() / "data" / "cache" / "inference"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve() if path.exists() else path
