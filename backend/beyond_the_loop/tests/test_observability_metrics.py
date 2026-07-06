"""Tests for the Prometheus metric definitions.

We check three things:
1. All expected metrics exist and are registered.
2. Label sets match the design (cardinality safety).
3. The /metrics endpoint returns valid Prometheus text WITHOUT a trailing
   slash — GMP scrapes hit the exact path, not a mount prefix.
"""
from fastapi import FastAPI
from starlette.testclient import TestClient

from beyond_the_loop.observability.metrics import (
    chat_completion_duration_seconds,
    chat_completions_total,
    http_request_duration_seconds,
    http_requests_total,
    metrics_endpoint,
    websocket_connections,
)


def test_http_request_metrics_have_expected_labels():
    assert set(http_request_duration_seconds._labelnames) == {"route", "method", "status_code"}
    assert set(http_requests_total._labelnames) == {"route", "method", "status_code"}


def test_chat_completion_metrics_have_expected_labels():
    assert set(chat_completion_duration_seconds._labelnames) == {"model", "phase"}
    assert set(chat_completions_total._labelnames) == {"model", "status"}


def test_websocket_gauge_has_no_labels():
    assert websocket_connections._labelnames == ()


def test_http_histogram_buckets_are_tuned_for_sub_second_traffic():
    # prometheus_client stores buckets as a list of floats with +Inf appended.
    upper_bounds = list(http_request_duration_seconds._upper_bounds)
    assert upper_bounds[:10] == [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]


def test_completion_histogram_buckets_are_tuned_for_multi_second_llm_calls():
    upper_bounds = list(chat_completion_duration_seconds._upper_bounds)
    assert upper_bounds[:10] == [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0]


def test_metrics_endpoint_serves_prometheus_text_at_exact_path():
    # Register the endpoint the way open_webui.main does — as a plain route,
    # not a Mount. This is the regression test for the SPA-catchall bug:
    # GMP hits /metrics (no trailing slash), so that path must serve
    # Prometheus text directly and never fall through to a catch-all.
    app = FastAPI()
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    with TestClient(app) as client:
        # Trigger one observation so at least one series has a sample.
        http_requests_total.labels(route="/test", method="GET", status_code="200").inc()

        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert "bchat_http_requests_total" in body
        assert 'route="/test"' in body
