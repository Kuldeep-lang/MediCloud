from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.timeutils import hospital_tz, local_day_bounds, local_today, now_utc
from app.models import Appointment, Doctor, Patient, User
from app.models.enums import ACTIVE_APPOINTMENT_STATUSES, AppointmentStatus, Role
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from app.services.common import get_or_404, like_term, paginate

ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CONFIRMED: {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW},
}


def _appointment_end():
    return Appointment.scheduled_at + func.make_interval(
        0, 0, 0, 0, 0, Appointment.duration_minutes
    )


def _lock_doctor(db: Session, doctor_id: int) -> Doctor:
    """Row-lock the doctor so concurrent bookings for the same doctor are serialised."""
    doctor = db.scalar(
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .with_for_update(of=Doctor)
        .execution_options(populate_existing=True)
    )
    if doctor is None:
        raise NotFoundError(f"Doctor {doctor_id} not found")
    return doctor


def _ensure_bookable(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: int,
    start: datetime,
    duration: int,
    exclude_id: int | None = None,
) -> None:
    if not doctor.is_active:
        raise BusinessRuleError("This doctor is no longer active")
    if start <= now_utc():
        raise BusinessRuleError("Appointments must be scheduled in the future")

    end = start + timedelta(minutes=duration)
    tz = hospital_tz()
    local_start, local_end = start.astimezone(tz), end.astimezone(tz)
    blocks = [b for b in doctor.schedules if b.day_of_week == local_start.weekday()]
    within_hours = local_start.date() == local_end.date() and any(
        b.start_time <= local_start.time() and local_end.time() <= b.end_time for b in blocks
    )
    if not within_hours:
        raise BusinessRuleError("The requested time is outside the doctor's working hours")

    def overlapping(column):
        stmt = select(Appointment.id).where(
            column,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.scheduled_at < end,
            _appointment_end() > start,
        )
        if exclude_id is not None:
            stmt = stmt.where(Appointment.id != exclude_id)
        return db.scalar(stmt.limit(1))

    if overlapping(Appointment.doctor_id == doctor.id):
        raise ConflictError("The doctor already has an appointment at this time")
    if overlapping(Appointment.patient_id == patient_id):
        raise ConflictError("The patient already has an appointment at this time")


def list_appointments(
    db: Session,
    *,
    day: date | None,
    date_from: date | None,
    date_to: date | None,
    doctor_id: int | None,
    patient_id: int | None,
    status: AppointmentStatus | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Appointment)
    if day:
        start, end = local_day_bounds(day)
        stmt = stmt.where(Appointment.scheduled_at >= start, Appointment.scheduled_at < end)
    if date_from:
        stmt = stmt.where(Appointment.scheduled_at >= local_day_bounds(date_from)[0])
    if date_to:
        stmt = stmt.where(Appointment.scheduled_at < local_day_bounds(date_to)[1])
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if search:
        term = like_term(search)
        stmt = stmt.join(Appointment.patient.of_type(Patient)).where(
            or_(
                Patient.first_name.ilike(term, escape="\\"),
                Patient.last_name.ilike(term, escape="\\"),
                Patient.patient_code.ilike(term, escape="\\"),
            )
        )
    ascending = day is not None or date_from is not None
    order = Appointment.scheduled_at.asc() if ascending else Appointment.scheduled_at.desc()
    return paginate(db, stmt.order_by(order, Appointment.id), page, page_size)


def create_appointment(db: Session, data: AppointmentCreate, user: User) -> Appointment:
    get_or_404(db, Patient, data.patient_id, "Patient")
    doctor = _lock_doctor(db, data.doctor_id)
    _ensure_bookable(
        db,
        doctor=doctor,
        patient_id=data.patient_id,
        start=data.scheduled_at,
        duration=data.duration_minutes,
    )
    appointment = Appointment(**data.model_dump(), created_by=user.id)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def update_appointment(db: Session, appt: Appointment, data: AppointmentUpdate) -> Appointment:
    if appt.status not in ACTIVE_APPOINTMENT_STATUSES:
        raise BusinessRuleError(f"A {appt.status.value} appointment cannot be changed")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    doctor_id = changes.get("doctor_id", appt.doctor_id)
    start = changes.get("scheduled_at", appt.scheduled_at)
    duration = changes.get("duration_minutes", appt.duration_minutes)
    if {"doctor_id", "scheduled_at", "duration_minutes"} & changes.keys():
        doctor = _lock_doctor(db, doctor_id)
        _ensure_bookable(
            db,
            doctor=doctor,
            patient_id=appt.patient_id,
            start=start,
            duration=duration,
            exclude_id=appt.id,
        )
    for key, value in changes.items():
        setattr(appt, key, value)
    db.commit()
    db.refresh(appt)
    return appt


def cancel_appointment(db: Session, appt: Appointment, reason: str | None) -> Appointment:
    if appt.status not in ACTIVE_APPOINTMENT_STATUSES:
        raise BusinessRuleError(f"A {appt.status.value} appointment cannot be cancelled")
    appt.status = AppointmentStatus.CANCELLED
    appt.cancellation_reason = reason
    db.commit()
    return appt


def update_status(
    db: Session, appt: Appointment, data: AppointmentStatusUpdate, user: User
) -> Appointment:
    target = AppointmentStatus(data.status)
    if user.role == Role.RECEPTIONIST and target == AppointmentStatus.COMPLETED:
        raise BusinessRuleError("Only doctors or admins can mark an appointment completed")
    if target not in ALLOWED_TRANSITIONS.get(appt.status, set()):
        raise BusinessRuleError(f"Cannot change status from {appt.status.value} to {target.value}")
    if target in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
        local_date = appt.scheduled_at.astimezone(hospital_tz()).date()
        if local_date > local_today():
            raise BusinessRuleError("Future appointments cannot be completed or marked no-show")
    appt.status = target
    if data.diagnosis is not None:
        appt.diagnosis = data.diagnosis
    if data.notes is not None:
        appt.notes = data.notes
    db.commit()
    return appt
