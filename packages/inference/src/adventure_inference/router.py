"""Select mission interpreter: auto (Ollama→rules), rules, or ollama."""

from __future__ import annotations

from typing import Literal

from adventure_core.intent import MissionIntent
from adventure_core.intent_validate import IntentValidationError, validate_and_repair_intent
from adventure_core.interpreters import interpret_rules
from adventure_core.polarity import repair_preference_inversions

from adventure_inference.errors import InferenceError
from adventure_inference.models_config import DEFAULT_MODEL, load_models_config, ollama_base_url
from adventure_inference.ollama_interpreter import interpret_ollama, ollama_available

InterpreterName = Literal["auto", "rules", "ollama"]


def interpret_mission(
    prompt: str,
    *,
    interpreter: InterpreterName = "auto",
    model: str | None = None,
    mode: str | None = None,
    allow_rules_fallback: bool = True,
    repair_polarity: bool = True,
    validate_intent: bool = True,
    base_url: str | None = None,
) -> MissionIntent:
    notes: list[str] = []
    intent: MissionIntent
    cfg = load_models_config()
    chosen_model = model or cfg.mission_interpreter or cfg.default_model or DEFAULT_MODEL
    url = ollama_base_url(base_url)

    if interpreter == "rules":
        intent = interpret_rules(prompt)
    elif interpreter == "ollama":
        if not ollama_available(url):
            raise InferenceError(
                f"Ollama is not reachable at {url}. "
                "Install from https://ollama.com , run `ollama serve`, "
                f"then `ollama pull {chosen_model}`. "
                "Or use `--interpreter rules` for offline/no-LLM. "
                "See docs/offline-inference.md."
            )
        try:
            intent = interpret_ollama(prompt, model=chosen_model, base_url=url)
        except IntentValidationError:
            raise
        except InferenceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise InferenceError(
                f"Ollama interpreter failed ({type(exc).__name__}: {exc}). "
                "Check the local daemon and model pin; see docs/offline-inference.md."
            ) from exc
    else:
        # auto
        if ollama_available(url):
            try:
                intent = interpret_ollama(prompt, model=chosen_model, base_url=url)
            except Exception as exc:  # noqa: BLE001
                if not allow_rules_fallback:
                    if isinstance(exc, InferenceError):
                        raise
                    raise InferenceError(
                        f"Ollama failed and --strict-llm is set ({type(exc).__name__}: {exc}). "
                        "Fix the local model or omit --strict-llm to fall back to rules."
                    ) from exc
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
                raise InferenceError(
                    f"Ollama unavailable at {url} and --strict-llm is set. "
                    f"Start Ollama and `ollama pull {chosen_model}`, "
                    "or omit --strict-llm / use `--interpreter rules`. "
                    "See docs/offline-inference.md."
                )
            intent = interpret_rules(prompt)
            intent = intent.model_copy(
                update={
                    "interpreter_notes": intent.interpreter_notes
                    + ["ollama_unavailable:using_rules"]
                }
            )

    intent = intent.model_copy(update={"raw_prompt": prompt})
    if validate_intent:
        intent = validate_and_repair_intent(intent)
    if repair_polarity:
        intent, _findings = repair_preference_inversions(intent, prompt=prompt)
    if mode:
        intent = intent.merge_mode_prior(mode)
    return intent
