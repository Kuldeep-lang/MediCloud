from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import AdminUser, ClinicalDeskUser, DbSession, Paging, StaffUser
from app.models import Doctor
from app.models.enums import Role
from app.schemas.appointment import AppointmentOut
from app.schemas.common import Page
from app.schemas.doctor import (
    AvailabilitySlot,
    DoctorCreate,
    DoctorDetail,
    DoctorOut,
    DoctorUpdate,
    ScheduleBlock,
    ScheduleOut,
)
from app.services import appointment_service, doctor_service
from app.services.common import get_or_404

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=Page[DoctorOut])
def list_doctors(
    _: StaffUser,
    db: DbSession,
    paging: Paging,
    search: Annotated[str | None, Query(max_length=100)] = None,
    department_id: int | None = None,
    specialization: Annotated[str | None, Query(max_length=100)] = None,
    include_inactive: bool = False,
) -> dict:
    return doctor_service.list_doctors(
        db,
        search=search,
        department_id=department_id,
        specialization=specialization,
        include_inactive=include_inactive,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("", response_model=DoctorDetail, status_code=status.HTTP_201_CREATED)
def create_doctor(body: DoctorCreate, _: AdminUser, db: DbSession) -> object:
    return doctor_service.create_doctor(db, body)


@router.get("/{doctor_id}", response_model=DoctorDetail)
def get_doctor(doctor_id: int, _: StaffUser, db: DbSession) -> object:
    return get_or_404(db, Doctor, doctor_id, "Doctor")


@router.patch("/{doctor_id}", response_model=DoctorDetail)
def update_doctor(doctor_id: int, body: DoctorUpdate, _: AdminUser, db: DbSession) -> object:
    doctor = get_or_404(db, Doctor, doctor_id, "Doctor")
    return doctor_service.update_doctor(db, doctor, body)


@router.delete("/{doctor_id}", response_model=DoctorOut)
def deactivate_doctor(doctor_id: int, _: AdminUser, db: DbSession) -> object:
    doctor = get_or_404(db, Doctor, doctor_id, "Doctor")
    return doctor_service.deactivate_doctor(db, doctor)


@router.get("/{doctor_id}/schedules", response_model=list[ScheduleOut])
def get_schedules(doctor_id: int, _: StaffUser, db: DbSession) -> list:
    return get_or_404(db, Doctor, doctor_id, "Doctor").schedules


@router.put("/{doctor_id}/schedules", response_model=list[ScheduleOut])
def replace_schedules(
    doctor_id: int, body: list[ScheduleBlock], user: ClinicalDeskUser, db: DbSession
) -> list:
    """Admins manage any schedule; doctors may edit only their own."""
    allowed = user.role == Role.ADMIN or (user.role == Role.DOCTOR and user.doctor_id == doctor_id)
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only edit your own schedule")
    doctor = get_or_404(db, Doctor, doctor_id, "Doctor")
    return doctor_service.replace_schedules(db, doctor, body).schedules


@router.get("/{doctor_id}/appointments", response_model=Page[AppointmentOut])
def doctor_appointments(
    doctor_id: int,
    user: ClinicalDeskUser,
    db: DbSession,
    paging: Paging,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> dict:
    if user.role == Role.DOCTOR and user.doctor_id != doctor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only view your own appointments")
    get_or_404(db, Doctor, doctor_id, "Doctor")
    return appointment_service.list_appointments(
        db,
        day=day,
        date_from=None,
        date_to=None,
        doctor_id=doctor_id,
        patient_id=None,
        status=None,
        search=None,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/{doctor_id}/availability", response_model=list[AvailabilitySlot])
def availability(
    doctor_id: int,
    _: ClinicalDeskUser,
    db: DbSession,
    day: Annotated[date, Query(alias="date")],
) -> list:
    doctor = get_or_404(db, Doctor, doctor_id, "Doctor")
    return doctor_service.availability(db, doctor, day)
