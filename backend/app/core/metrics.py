"""Prometheus instrumentation.

* ``PrometheusMiddleware`` records request count, latency and in-flight requests,
  labelled by the *route template* (e.g. ``/api/v1/patients/{patient_id}``) so label
  cardinality stays bounded regardless of IDs in URLs.
* ``DatabaseCollector`` reports DB connectivity and a few business gauges at scrape time.
"""

import platform
import socket
import time

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "route", "status"])
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
IN_PROGRESS = Gauge("http_requests_in_progress", "HTTP requests currently being served", ["method"])
BUILD_INFO = Gauge(
    "medicloud_build_info", "Build information (value is always 1)", ["version", "commit", "env"]
)

STARTED_AT = time.time()
HOSTNAME = socket.gethostname()
PYTHON_VERSION = platform.python_version()

# Simple in-process counters surfaced by /api/v1/system/status (per pod).
request_stats = {"total": 0, "errors_5xx": 0}


def _route_template(scope: Scope) -> str:
    """Rebuild the route template after routing, e.g. /api/v1/patients/{patient_id}.

    Uses the matched route's path_params rather than framework internals, so it keeps
    working across FastAPI versions. Unmatched paths (404 scans, bots) collapse into a
    single "unmatched" label value to keep Prometheus label cardinality bounded.
    """
    if scope.get("route") is None:
        return "unmatched"
    params = scope.get("path_params") or {}
    if not params:
        return scope["path"]
    by_value = {str(value): name for name, value in params.items()}
    segments = [
        "{" + by_value.pop(segment) + "}" if segment in by_value else segment
        for segment in scope["path"].split("/")
    ]
    return "/".join(segments)


class PrometheusMiddleware:
    """Pure ASGI middleware (avoids BaseHTTPMiddleware's streaming quirks)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        IN_PROGRESS.labels(method).inc()
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route = _route_template(scope)  # scope now carries the matched route
            IN_PROGRESS.labels(method).dec()
            REQUEST_COUNT.labels(method, route, str(status_code)).inc()
            REQUEST_LATENCY.labels(method, route).observe(elapsed)
            request_stats["total"] += 1
            if status_code >= 500:
                request_stats["errors_5xx"] += 1


class DatabaseCollector(Collector):
    """Collected on every scrape: DB reachability, ping latency and business gauges."""

    def describe(self):  # avoid running collect() at registration time
        return []

    def collect(self):
        from sqlalchemy import func, select, text

        from app.core.timeutils import local_day_bounds, local_today
        from app.db.session import engine
        from app.models import Appointment, Bed
        from app.models.enums import AppointmentStatus, BedStatus

        up = GaugeMetricFamily("medicloud_db_up", "1 if the database is reachable, else 0")
        ping = GaugeMetricFamily("medicloud_db_ping_seconds", "Database round-trip time")
        beds = GaugeMetricFamily("medicloud_beds_occupied", "Currently occupied beds")
        appts = GaugeMetricFamily("medicloud_appointments_today", "Appointments today")
        try:
            with engine.connect() as conn:
                t0 = time.perf_counter()
                conn.execute(text("SELECT 1"))
                ping.add_metric([], time.perf_counter() - t0)
                up.add_metric([], 1)
                beds.add_metric(
                    [],
                    conn.scalar(select(func.count(Bed.id)).where(Bed.status == BedStatus.OCCUPIED))
                    or 0,
                )
                start, end = local_day_bounds(local_today())
                appts.add_metric(
                    [],
                    conn.scalar(
                        select(func.count(Appointment.id)).where(
                            Appointment.scheduled_at >= start,
                            Appointment.scheduled_at < end,
                            Appointment.status != AppointmentStatus.CANCELLED,
                        )
                    )
                    or 0,
                )
        except Exception:  # noqa: BLE001 - any DB failure means "down"
            up.add_metric([], 0)
        yield up
        yield ping
        yield beds
        yield appts


_registered = False


def register_collectors(version: str, commit: str, env: str) -> None:
    """Idempotent: safe when the app factory runs more than once (tests)."""
    global _registered
    BUILD_INFO.labels(version, commit, env).set(1)
    if not _registered:
        REGISTRY.register(DatabaseCollector())
        _registered = True
