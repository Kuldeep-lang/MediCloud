"""Probe and metrics endpoints (outside /api, never routed through the public Ingress)."""

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"], include_in_schema=False)


@router.get("/health/live")
def live() -> dict:
    """Liveness: the process is up. Deliberately does NOT check the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> Response:
    """Readiness: can we serve traffic? Requires a working database connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(
            {"status": "unavailable", "database": "down"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ok", "database": "up"})


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
