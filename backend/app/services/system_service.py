import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import get_settings


def database_status(db: Session) -> dict:
    try:
        start = time.perf_counter()
        version = db.execute(text("SHOW server_version")).scalar()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "up", "latency_ms": latency_ms, "server_version": version}
    except Exception as exc:  # noqa: BLE001 - surfaced to admins as a status, not raised
        return {"status": "down", "latency_ms": None, "error": type(exc).__name__}


def status(db: Session) -> dict:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "commit": settings.git_commit,
        "environment": settings.app_env,
        "hostname": metrics.HOSTNAME,
        "python_version": metrics.PYTHON_VERSION,
        "started_at": metrics.STARTED_AT,
        "uptime_seconds": round(time.time() - metrics.STARTED_AT),
        "timezone": settings.hospital_timezone,
        "database": database_status(db),
        "requests": dict(metrics.request_stats),
    }


def public_info() -> dict:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "currency": settings.currency,
        "timezone": settings.hospital_timezone,
    }
