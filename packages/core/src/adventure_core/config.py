"""Load Region Pack manifests and Discovery Mode weight profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from adventure_core.pack_manifest import PackManifest, PackSource

# Re-export for callers
__all__ = [
    "PackManifest",
    "PackSource",
    "ModeWeights",
    "repo_root",
    "configs_dir",
    "load_yaml",
    "load_pack_manifest",
    "load_mode",
]


class ModeWeights(BaseModel):
    mode_id: str
    description: str = ""
    weights: dict[str, float] = Field(default_factory=dict)
    risk_weight: float = 1.0
    restriction_weight: float = 1.0
    gates: dict[str, float] = Field(default_factory=dict)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "configs" / "modes").is_dir() and (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not locate Adventure AI repo root (configs/modes missing)")


def configs_dir() -> Path:
    return repo_root() / "configs"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_pack_manifest(pack_id_or_path: str) -> tuple[PackManifest, Path]:
    """Resolve pack id/path → (manifest, pack_dir).

    Search order:
      1. Directory with pack.yaml
      2. data/packs/<id>/
      3. configs/packs/<id>.yaml → fixtures_dir or data/packs
      4. fixtures/<id>/
    """
    root = repo_root()
    path = Path(pack_id_or_path)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(root / path)

    for cand in candidates:
        if cand.is_dir() and (cand / "pack.yaml").exists():
            data = load_yaml(cand / "pack.yaml")
            return PackManifest.model_validate(data), cand.resolve()

    pack_id = pack_id_or_path

    data_pack = root / "data" / "packs" / pack_id
    if data_pack.is_dir() and (data_pack / "pack.yaml").exists():
        data = load_yaml(data_pack / "pack.yaml")
        return PackManifest.model_validate(data), data_pack.resolve()

    config_path = configs_dir() / "packs" / f"{pack_id}.yaml"
    if config_path.exists():
        data = load_yaml(config_path)
        manifest = PackManifest.model_validate(data)
        if manifest.synthetic or manifest.fixtures_dir:
            fixtures = root / (manifest.fixtures_dir or f"fixtures/{manifest.pack_id}")
            if fixtures.is_dir():
                # Prefer built pack if present
                built = root / (manifest.output_dir or f"data/packs/{manifest.pack_id}")
                if built.is_dir() and (built / "pack.yaml").exists() and not manifest.synthetic:
                    built_data = load_yaml(built / "pack.yaml")
                    return PackManifest.model_validate(built_data), built.resolve()
                return manifest, fixtures.resolve()
        built = root / (manifest.output_dir or f"data/packs/{manifest.pack_id}")
        if built.is_dir() and (built / "pack.yaml").exists():
            built_data = load_yaml(built / "pack.yaml")
            return PackManifest.model_validate(built_data), built.resolve()
        raise FileNotFoundError(
            f"Pack '{pack_id}' is configured but not built yet. "
            f"Build it with: adventurectl pack build --config {pack_id} "
            f"(requires osmium-tool on PATH). "
            f"For offline/CI, pass a fixture instead: "
            f"--pack fixtures/karakoram_mini"
        )

    fixtures = root / "fixtures" / pack_id
    if fixtures.is_dir() and (fixtures / "pack.yaml").exists():
        data = load_yaml(fixtures / "pack.yaml")
        # mark synthetic if missing
        if "synthetic" not in data:
            data["synthetic"] = True
        return PackManifest.model_validate(data), fixtures.resolve()

    raise FileNotFoundError(f"Unknown pack: {pack_id_or_path}")


def load_mode(mode_id: str) -> ModeWeights:
    path = configs_dir() / "modes" / f"{mode_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown discovery mode: {mode_id} ({path})")
    data = load_yaml(path)
    return ModeWeights.model_validate(data)
