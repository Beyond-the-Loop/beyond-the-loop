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
from prometheus_client import Counter, Gauge, Histogram, start_http_server

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

# Metrics are exposed on a dedicated port that is NOT reachable via the
# GCE ingress. GMP scrapes the pod IP directly on this port. Serving on
# a second port (rather than adding /metrics to the FastAPI app) means:
# - no risk of leaking metrics to the public internet
# - no Cloud Armor / auth workaround needed
# - no interference with FastAPI's mount routing (Mount /metrics silently
#   fell through to the SPA catch-all before this change)
METRICS_PORT = 9090


def start_metrics_server(port: int = METRICS_PORT) -> None:
    """Start a background WSGI HTTP server exposing the default registry.

    Called once from main.py's lifespan startup. The server runs in a
    daemon thread; on pod shutdown Kubernetes SIGKILLs the process and
    the OS reclaims the port.
    """
    start_http_server(port)
