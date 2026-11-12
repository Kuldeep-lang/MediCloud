from fastapi import APIRouter

from app.api.v1.routes import (
    appointments,
    auth,
    billing,
    dashboard,
    departments,
    doctors,
    patients,
    pharmacy,
    system,
    users,
    wards,
)

api_router = APIRouter()
for module in (
    auth,
    users,
    departments,
    patients,
    doctors,
    appointments,
    wards,
    pharmacy,
    billing,
    dashboard,
    system,
):
    api_router.include_router(module.router)
