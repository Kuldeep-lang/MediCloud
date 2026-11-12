from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import ClinicalDeskUser, DbSession, FrontDeskUser, Paging, scoped_doctor_id
from app.models import Appointment, User
from app.models.enums import AppointmentStatus, Role
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from app.schemas.common import Page
from app.services import appointment_service
from app.services.common import get_or_404

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _get_visible(db, appointment_id: int, user: User) -> Appointment:
    appt = get_or_404(db, Appointment, appointment_id, "Appointment")
    if user.role == Role.DOCTOR and appt.doctor_id != user.doctor_id:
        # Do not reveal that the appointment exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Appointment {appointment_id} not found")
    return appt


@router.get("", response_model=Page[AppointmentOut])
def list_appointments(
    user: ClinicalDeskUser,
    db: DbSession,
    paging: Paging,
    day: Annotated[date | None, Query(alias="date")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    status: AppointmentStatus | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    return appointment_service.list_appointments(
        db,
        day=day,
        date_from=date_from,
        date_to=date_to,
        doctor_id=scoped_doctor_id(user, doctor_id),
        patient_id=patient_id,
        status=status,
        search=search,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(body: AppointmentCreate, user: FrontDeskUser, db: DbSession) -> object:
    return appointment_service.create_appointment(db, body, user)


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, user: ClinicalDeskUser, db: DbSession) -> object:
    return _get_visible(db, appointment_id, user)


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: int, body: AppointmentUpdate, _: FrontDeskUser, db: DbSession
) -> object:
    appt = get_or_404(db, Appointment, appointment_id, "Appointment")
    return appointment_service.update_appointment(db, appt, body)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int, body: AppointmentCancel, _: FrontDeskUser, db: DbSession
) -> object:
    appt = get_or_404(db, Appointment, appointment_id, "Appointment")
    return appointment_service.cancel_appointment(db, appt, body.reason)


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def update_status(
    appointment_id: int, body: AppointmentStatusUpdate, user: ClinicalDeskUser, db: DbSession
) -> object:
    appt = _get_visible(db, appointment_id, user)
    return appointment_service.update_status(db, appt, body, user)
