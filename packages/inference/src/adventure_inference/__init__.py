"""Local inference adapters (Ollama). LLM translates language → MissionIntent only."""

from adventure_inference.errors import InferenceError
from adventure_inference.models_config import load_models_config, ollama_base_url
from adventure_inference.ollama_interpreter import interpret_ollama, ollama_available
from adventure_inference.paths import inference_cache_dir
from adventure_inference.router import interpret_mission

__all__ = [
    "InferenceError",
    "inference_cache_dir",
    "interpret_mission",
    "interpret_ollama",
    "load_models_config",
    "ollama_available",
    "ollama_base_url",
]
