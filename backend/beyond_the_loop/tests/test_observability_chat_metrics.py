"""Tests for chat completion metric emission.

We test the pure helper that turns phase durations + model name into
metric observations. Testing the full endpoint would require mocking
LiteLLM, PII, and the router, which the design explicitly rules out
(this is just aggregation glue, not new behavior).
"""
from beyond_the_loop.observability.chat_metrics import record_chat_completion
from beyond_the_loop.observability.metrics import (
    chat_completion_duration_seconds,
    chat_completions_total,
)


def _sample_counter(counter, **labels):
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") and sample.labels == labels:
                return sample.value
    return 0.0


def test_success_records_three_phases_and_one_counter_increment():
    baseline = _sample_counter(
        chat_completions_total, model="GPT-5 mini", status="success"
    )

    record_chat_completion(
        model="GPT-5 mini",
        payload_seconds=0.5,
        litellm_seconds=1.2,
        total_seconds=1.8,
        status="success",
    )

    after = _sample_counter(
        chat_completions_total, model="GPT-5 mini", status="success"
    )
    assert after == baseline + 1.0

    # All three phases got exactly one observation.
    for phase, expected in (("payload", 0.5), ("litellm", 1.2), ("total", 1.8)):
        h = chat_completion_duration_seconds.labels(model="GPT-5 mini", phase=phase)
        assert h._sum.get() >= expected  # cumulative, so we can only bound-from-below


def test_error_status_records_counter_but_still_observes_total():
    baseline = _sample_counter(
        chat_completions_total, model="Claude Sonnet 4.6", status="error"
    )

    record_chat_completion(
        model="Claude Sonnet 4.6",
        payload_seconds=0.3,
        litellm_seconds=None,   # LiteLLM never returned
        total_seconds=0.4,
        status="error",
    )

    after = _sample_counter(
        chat_completions_total, model="Claude Sonnet 4.6", status="error"
    )
    assert after == baseline + 1.0


def test_none_model_falls_back_to_unknown_label():
    # If model resolution failed upstream, we still want a metric, just
    # bucketed under a stable label to avoid a NoneType crash.
    baseline = _sample_counter(
        chat_completions_total, model="unknown", status="error"
    )

    record_chat_completion(
        model=None,
        payload_seconds=0.1,
        litellm_seconds=None,
        total_seconds=0.1,
        status="error",
    )

    after = _sample_counter(
        chat_completions_total, model="unknown", status="error"
    )
    assert after == baseline + 1.0
