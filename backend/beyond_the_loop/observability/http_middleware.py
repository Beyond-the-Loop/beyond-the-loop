"""ASGI middleware that records Prometheus HTTP metrics.

We ONLY record aggregated metrics here — the existing JSON access log in
open_webui.main stays intact and continues to emit `event=http_request`
lines for debugging and trace correlation.

Route label: we use the FastAPI/Starlette route template
(`/items/{item_id}`) instead of the raw path. Starlette populates
`scope["route"]` after the router matches, which happens during
`call_next`. For 404s or unmatched paths, we use the literal string
"unmatched" — bounded — so we still get visibility into 404 rates
without exploding cardinality.
"""
import time

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from beyond_the_loop.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)


def _route_template(request: Request) -> str:
    """Return the matched route template, or 'unmatched'.

    Starlette sets scope["route"] to the matched routing entry. For a
    Route this is `/items/{item_id}`; for a Mount (e.g. `/metrics`,
    `/ws`) the sub-app owns any deeper routing and we can only see the
    mount prefix. Mount paths are literals declared in main.py — bounded
    — so exposing them as labels is cardinality-safe.
    """
    route = request.scope.get("route")
    if isinstance(route, Route):
        return route.path
    if isinstance(route, Mount):
        return route.path or "unmatched"
    return "unmatched"


async def prometheus_http_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
        status_code = response.status_code
    except Exception:
        # Something inside the app tree raised. Record it as 500 so the
        # metric reflects the true user-visible failure, then re-raise
        # for the framework's own error handling.
        duration = time.perf_counter() - start
        route = _route_template(request)
        http_requests_total.labels(
            route=route, method=request.method, status_code="500"
        ).inc()
        http_request_duration_seconds.labels(
            route=route, method=request.method, status_code="500"
        ).observe(duration)
        raise

    duration = time.perf_counter() - start
    route = _route_template(request)
    status_str = str(status_code)
    http_requests_total.labels(
        route=route, method=request.method, status_code=status_str
    ).inc()
    http_request_duration_seconds.labels(
        route=route, method=request.method, status_code=status_str
    ).observe(duration)
    return response
