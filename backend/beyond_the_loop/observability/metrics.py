"""Prometheus metric definitions for the Beyond the Loop backend.

Cardinality safety — the labels below are intentionally low-cardinality:
- route: FastAPI route template (bounded by number of registered endpoints)
- method: HTTP verb (~7 values)
- status_code: HTTP status (~30 values)
- model: configured LLM name (bounded, ~10-20)
- phase: fixed set {total, litellm, payload}
- status: fixed set {success, error}

Never add task_id, user_id, chat_id, trace_id, or any user-supplied value
as a label — that would explode series count and either kill GMP or the
budget.
"""
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

# HTTP request instrumentation — driven from access_log_middleware.
HTTP_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

http_request_duration_seconds = Histogram(
    "bchat_http_request_duration_seconds",
    "HTTP request duration in seconds by route, method, and status.",
    labelnames=("route", "method", "status_code"),
    buckets=HTTP_BUCKETS,
)

http_requests_total = Counter(
    "bchat_http_requests_total",
    "HTTP requests processed by route, method, and status.",
    labelnames=("route", "method", "status_code"),
)

# Chat completion instrumentation — driven from the chat_enqueue log site.
COMPLETION_BUCKETS = (0.1, 0.5, 1, 2, 5, 10, 20, 30, 60, 120)

chat_completion_duration_seconds = Histogram(
    "bchat_chat_completion_duration_seconds",
    "Chat completion duration in seconds by model and phase.",
    labelnames=("model", "phase"),
    buckets=COMPLETION_BUCKETS,
)

chat_completions_total = Counter(
    "bchat_chat_completions_total",
    "Chat completions by model and outcome.",
    labelnames=("model", "status"),
)

# Real-time WebSocket presence — driven from Socket.IO connect/disconnect handlers.
websocket_connections = Gauge(
    "bchat_websocket_connections",
    "Currently open WebSocket connections.",
)

# /metrics endpoint. Implemented as a plain route (not `make_asgi_app`'s
# Mount) because Starlette's Mount only matches sub-paths — a request to
# `/metrics` without a trailing slash falls through to the SPA static
# mount at `/` and returns index.html. GMP scrapes hit `/metrics`
# without a slash, so the Mount version silently returned HTML in
# production. The default REGISTRY still gives us Python process
# metrics (GC, memory, threads) for free.
def metrics_endpoint() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
