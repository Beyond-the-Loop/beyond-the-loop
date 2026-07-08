"""Tests for the Prometheus metric definitions.

We check three things:
1. All expected metrics exist and are registered.
2. Label sets match the design (cardinality safety).
3. The dedicated metrics HTTP server (started on port 9090 at app boot
   from a lifespan hook) actually serves the default registry over HTTP.
"""
import socket
import time
from urllib.request import urlopen

from prometheus_client import generate_latest

from beyond_the_loop.observability.metrics import (
    chat_completion_duration_seconds,
    chat_completions_total,
    http_request_duration_seconds,
    http_requests_total,
    start_metrics_server,
    websocket_connections,
)


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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


def test_generate_latest_includes_bchat_series():
    # Direct check on the default registry — no HTTP round-trip needed to
    # verify the metrics are registered and serialisable.
    http_requests_total.labels(route="/test-a", method="GET", status_code="200").inc()
    body = generate_latest().decode("utf-8")
    assert "bchat_http_requests_total" in body
    assert 'route="/test-a"' in body


def test_start_metrics_server_serves_prometheus_text_over_http():
    # Regression test for the port-9090 sidecar server: starting it must
    # actually bind and serve the default registry. Using a random free
    # port keeps the test hermetic; the production default is 9090.
    port = _find_free_port()
    start_metrics_server(port=port)

    # start_http_server returns immediately after binding; give the
    # thread a beat to be ready to accept.
    time.sleep(0.05)

    http_requests_total.labels(route="/test-b", method="GET", status_code="200").inc()

    with urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")

    assert "bchat_http_requests_total" in body
    assert 'route="/test-b"' in body
