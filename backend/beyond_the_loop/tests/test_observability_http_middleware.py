"""Tests for HTTP metric emission from access_log_middleware.

Cardinality-critical checks:
- Matched routes emit the *template* (/items/{id}), not the raw path.
- Unmatched routes (404) emit the literal "unmatched" — bounded — never
  the raw path.
"""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from beyond_the_loop.observability.http_middleware import prometheus_http_middleware
from beyond_the_loop.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)


def _sample_counter(counter, **labels):
    """Return the counter value for a given label combination, or 0.0."""
    for sample_labels, sample_value in _iter_counter_samples(counter):
        if sample_labels == labels:
            return sample_value
    return 0.0


def _iter_counter_samples(counter):
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                yield sample.labels, sample.value


@pytest.fixture
def app():
    app = FastAPI()
    app.middleware("http")(prometheus_http_middleware)

    @app.get("/items/{item_id}")
    def _read_item(item_id: str):
        return {"id": item_id}

    return app


def test_matched_route_records_template_not_raw_path(app):
    client = TestClient(app)

    baseline = _sample_counter(
        http_requests_total,
        route="/items/{item_id}",
        method="GET",
        status_code="200",
    )

    r = client.get("/items/abc-123")
    assert r.status_code == 200

    after = _sample_counter(
        http_requests_total,
        route="/items/{item_id}",
        method="GET",
        status_code="200",
    )
    assert after == baseline + 1.0

    # The raw-path label must NEVER appear — that would be a cardinality bug.
    raw = _sample_counter(
        http_requests_total,
        route="/items/abc-123",
        method="GET",
        status_code="200",
    )
    assert raw == 0.0


def test_unmatched_route_falls_back_to_unmatched_label(app):
    client = TestClient(app)

    baseline = _sample_counter(
        http_requests_total,
        route="unmatched",
        method="GET",
        status_code="404",
    )

    r = client.get("/no/such/path/xyz")
    assert r.status_code == 404

    after = _sample_counter(
        http_requests_total,
        route="unmatched",
        method="GET",
        status_code="404",
    )
    assert after == baseline + 1.0


def test_duration_histogram_is_observed(app):
    client = TestClient(app)

    baseline_count = http_request_duration_seconds.labels(
        route="/items/{item_id}", method="GET", status_code="200"
    )._sum.get()

    client.get("/items/abc-123")

    after_count = http_request_duration_seconds.labels(
        route="/items/{item_id}", method="GET", status_code="200"
    )._sum.get()

    # The bucket sum grew, confirming an observation was recorded.
    assert after_count > baseline_count
