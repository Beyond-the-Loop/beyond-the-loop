"""Helper to record chat completion metrics.

Extracted from the request handler to keep main.py readable and to give
the emission logic a clean unit-test surface. `total_seconds` is always
observed; `payload_seconds` and `litellm_seconds` are observed only when
their phase actually completed (a request that errors in payload
processing never reaches LiteLLM, and we shouldn't invent a zero).
"""
from typing import Optional

from beyond_the_loop.observability.metrics import (
    chat_completion_duration_seconds,
    chat_completions_total,
)


def record_chat_completion(
    *,
    model: Optional[str],
    payload_seconds: Optional[float],
    litellm_seconds: Optional[float],
    total_seconds: float,
    status: str,
) -> None:
    label_model = model if model else "unknown"

    chat_completions_total.labels(model=label_model, status=status).inc()

    chat_completion_duration_seconds.labels(
        model=label_model, phase="total"
    ).observe(total_seconds)

    if payload_seconds is not None:
        chat_completion_duration_seconds.labels(
            model=label_model, phase="payload"
        ).observe(payload_seconds)

    if litellm_seconds is not None:
        chat_completion_duration_seconds.labels(
            model=label_model, phase="litellm"
        ).observe(litellm_seconds)
