"""Gitignored cache layout for Adventure-managed inference artifacts.

Ollama model weights live in Ollama's own store (typically ``~/.ollama``), not
in the repo. This package only manages *our* caches under ``data/cache/``.
"""

from __future__ import annotations

import os
from pathlib import Path

from adventure_core.config import repo_root

from adventure_inference.models_config import load_models_config


def inference_cache_dir(*, create: bool = False) -> Path:
    """Return the Adventure inference cache directory.

    Resolution order:
      1. ``ADVENTURE_INFERENCE_CACHE``
      2. ``configs/models.yaml`` → ``cache.inference_dir`` (relative to repo root
         unless absolute)
      3. ``data/cache/inference``
    """
    override = os.environ.get("ADVENTURE_INFERENCE_CACHE", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        configured = load_models_config().cache_inference_dir.strip() or "data/cache/inference"
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = repo_root() / path
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve() if path.exists() else path
