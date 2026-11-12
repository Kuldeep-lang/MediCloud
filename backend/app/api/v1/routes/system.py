from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession
from app.services import system_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
def info() -> dict:
    """Public, non-sensitive app info (name, version, currency, timezone)."""
    return system_service.public_info()


@router.get("/status")
def status(_: AdminUser, db: DbSession) -> dict:
    """Runtime status of the pod that served the request (shows load balancing)."""
    return system_service.status(db)
