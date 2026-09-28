"""Helpers for reading google-genai responses, shared by the Gemini-backed parsers."""

from __future__ import annotations

from typing import Any


def finish_reason(response: Any) -> str | None:
    """The first candidate's finish reason as a plain string, e.g. "STOP" or "MAX_TOKENS"."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    # The SDK's FinishReason is a str enum; fakes and older SDKs pass plain strings.
    return str(getattr(reason, "value", reason)) if reason is not None else None
