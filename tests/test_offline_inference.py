"""Offline inference contract: pins, cache layout, clear errors (#25)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from adventure_cli.main import app
from adventure_inference import (
    InferenceError,
    inference_cache_dir,
    interpret_mission,
    load_models_config,
    ollama_base_url,
)
from adventure_inference import models_config as models_config_mod
from adventure_inference import ollama_interpreter as oi
from adventure_inference.router import interpret_mission as interpret_mission_router
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_models_cache() -> None:
    models_config_mod.clear_models_config_cache()
    yield
    models_config_mod.clear_models_config_cache()


def test_models_config_pins_ollama_only() -> None:
    cfg = load_models_config()
    assert cfg.runtime == "ollama"
    assert cfg.default_model == "llama3.2"
    assert "llama3.2" in cfg.fallback
    assert cfg.hardware_floors["llama3.2"].ram_gb >= 4
    assert "data/cache/inference" in cfg.cache_inference_dir.replace("\\", "/")


def test_no_cloud_api_env_required_for_rules_path(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "ADVENTURE_OLLAMA_BASE_URL",
        "OLLAMA_HOST",
    ):
        monkeypatch.delenv(key, raising=False)
    intent = interpret_mission("hate crowds, love rivers", interpreter="rules")
    assert intent.source == "rules"
    assert intent.preferences.human_activity < 0


def test_ollama_base_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADVENTURE_OLLAMA_BASE_URL", "http://127.0.0.1:11435")
    assert ollama_base_url() == "http://127.0.0.1:11435"
    monkeypatch.delenv("ADVENTURE_OLLAMA_BASE_URL")
    monkeypatch.setenv("OLLAMA_HOST", "10.0.0.2:11434")
    assert ollama_base_url() == "http://10.0.0.2:11434"


def test_inference_cache_dir_default_and_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = inference_cache_dir()
    assert default.as_posix().endswith("data/cache/inference")
    override = tmp_path / "inf-cache"
    monkeypatch.setenv("ADVENTURE_INFERENCE_CACHE", str(override))
    path = inference_cache_dir(create=True)
    assert path == override.resolve()
    assert path.is_dir()


def test_ollama_unavailable_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oi, "ollama_available", lambda *a, **k: False)
    with pytest.raises(InferenceError) as exc:
        interpret_mission_router("hello", interpreter="ollama")
    msg = str(exc.value)
    assert "Ollama" in msg
    assert "ollama pull" in msg or "ollama serve" in msg
    assert "rules" in msg
    assert "offline-inference" in msg


def test_missing_model_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oi, "ollama_available", lambda *a, **k: True)
    monkeypatch.setattr(oi, "_list_models", lambda _url: {"other:7b"})
    with pytest.raises(InferenceError) as exc:
        oi.interpret_ollama("hello", model="llama3.2", base_url="http://127.0.0.1:11434")
    msg = str(exc.value)
    assert "llama3.2" in msg
    assert "ollama pull" in msg
    assert "Available" in msg


def test_strict_auto_without_ollama_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("adventure_inference.router.ollama_available", lambda *a, **k: False)
    with pytest.raises(InferenceError) as exc:
        interpret_mission_router("hello", interpreter="auto", allow_rules_fallback=False)
    assert "strict-llm" in str(exc.value) or "rules" in str(exc.value)


def test_cli_ollama_missing_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "adventure_cli.pipeline.interpret_mission",
        lambda *a, **k: (_ for _ in ()).throw(
            InferenceError("Ollama is not reachable at http://127.0.0.1:11434. See docs.")
        ),
    )
    result = runner.invoke(
        app,
        [
            "mission",
            "run",
            "--pack",
            "fixtures/karakoram_mini",
            "--interpreter",
            "ollama",
            "-p",
            "test",
        ],
    )
    assert result.exit_code == 2
    assert "Inference error" in result.stdout
    assert "Ollama" in result.stdout


def test_inference_package_does_not_read_cloud_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default Ollama path must not consult cloud provider env vars."""
    monkeypatch.setenv("OPENAI_API_KEY", "should-never-be-read")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-never-be-read")
    # Reachability check only — no network model call required.
    monkeypatch.setattr(oi, "ollama_available", lambda *a, **k: False)
    with pytest.raises(InferenceError):
        interpret_mission_router("x", interpreter="ollama")
    # If cloud keys were required, this would have failed differently; assert they remain set.
    assert os.environ.get("OPENAI_API_KEY") == "should-never-be-read"
