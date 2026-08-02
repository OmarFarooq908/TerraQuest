"""Actionable failures for local-only inference paths."""

from __future__ import annotations


class InferenceError(RuntimeError):
    """Local inference could not run; message should tell the user how to recover."""
