"""Local inference adapters (Ollama). LLM translates language → MissionIntent only."""

from adventure_inference.ollama_interpreter import interpret_ollama, ollama_available
from adventure_inference.router import interpret_mission

__all__ = ["interpret_mission", "interpret_ollama", "ollama_available"]
