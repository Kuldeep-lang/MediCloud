from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, DbSession, StaffUser
from app.models.enums import Role
from app.schemas.dashboard import (
    AdmissionTrendPoint,
    AppointmentStats,
    DashboardSummary,
    DepartmentCount,
    RevenuePoint,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, response_model_exclude_none=True)
def summary(user: StaffUser, db: DbSession) -> dict:
    """KPIs for the signed-in role. Revenue is visible to admins only."""
    return dashboard_service.summary(
        db,
        include_revenue=user.role == Role.ADMIN,
        include_billing=user.role in (Role.ADMIN, Role.RECEPTIONIST),
        doctor_id=user.doctor_id if user.role == Role.DOCTOR else None,
    )


@router.get("/admissions-trend", response_model=list[AdmissionTrendPoint])
def admissions_trend(
    _: StaffUser, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30
) -> list:
    return dashboard_service.admissions_trend(db, days)


@router.get("/appointment-stats", response_model=AppointmentStats)
def appointment_stats(
    _: StaffUser, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30
) -> dict:
    return dashboard_service.appointment_stats(db, days)


@router.get("/department-distribution", response_model=list[DepartmentCount])
def department_distribution(
    _: StaffUser, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 90
) -> list:
    return dashboard_service.department_distribution(db, days)


@router.get("/revenue", response_model=list[RevenuePoint])
def revenue(_: AdminUser, db: DbSession, months: Annotated[int, Query(ge=1, le=24)] = 6) -> list:
    return dashboard_service.revenue_by_month(db, months)
