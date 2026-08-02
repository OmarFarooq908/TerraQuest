"""Select mission interpreter: auto (Ollama→rules), rules, or ollama."""

from __future__ import annotations

from typing import Literal

from adventure_core.intent import MissionIntent
from adventure_core.interpreters import interpret_rules
from adventure_core.polarity import repair_preference_inversions

from adventure_inference.ollama_interpreter import interpret_ollama, ollama_available

InterpreterName = Literal["auto", "rules", "ollama"]


def interpret_mission(
    prompt: str,
    *,
    interpreter: InterpreterName = "auto",
    model: str = "llama3.2",
    mode: str | None = None,
    allow_rules_fallback: bool = True,
    repair_polarity: bool = True,
) -> MissionIntent:
    notes: list[str] = []
    intent: MissionIntent

    if interpreter == "rules":
        intent = interpret_rules(prompt)
    elif interpreter == "ollama":
        if not ollama_available():
            raise RuntimeError("Ollama not available at http://127.0.0.1:11434")
        intent = interpret_ollama(prompt, model=model)
    else:
        # auto
        if ollama_available():
            try:
                intent = interpret_ollama(prompt, model=model)
            except Exception as exc:  # noqa: BLE001
                if not allow_rules_fallback:
                    raise
                notes.append(f"ollama_failed:{type(exc).__name__}:falling_back_to_rules")
                intent = interpret_rules(prompt)
                intent = intent.model_copy(
                    update={
                        "source": "hybrid",
                        "interpreter_notes": intent.interpreter_notes + notes,
                    }
                )
        else:
            if not allow_rules_fallback:
                raise RuntimeError(
                    "Ollama unavailable and allow_rules_fallback=False (interpreter=auto)."
                )
            intent = interpret_rules(prompt)
            intent = intent.model_copy(
                update={
                    "interpreter_notes": intent.interpreter_notes
                    + ["ollama_unavailable:using_rules"]
                }
            )

    intent = intent.model_copy(update={"raw_prompt": prompt})
    if repair_polarity:
        intent, _findings = repair_preference_inversions(intent, prompt=prompt)
    if mode:
        intent = intent.merge_mode_prior(mode)
    return intent
