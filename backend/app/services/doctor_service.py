from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.timeutils import hospital_tz, local_day_bounds, now_utc
from app.models import Appointment, Department, Doctor, DoctorSchedule, User
from app.models.enums import ACTIVE_APPOINTMENT_STATUSES, Role
from app.schemas.doctor import DoctorCreate, DoctorUpdate, ScheduleBlock
from app.services.common import like_term, paginate


def list_doctors(
    db: Session,
    *,
    search: str | None,
    department_id: int | None,
    specialization: str | None,
    include_inactive: bool,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Doctor).order_by(Doctor.last_name, Doctor.first_name)
    if not include_inactive:
        stmt = stmt.where(Doctor.is_active.is_(True))
    if department_id:
        stmt = stmt.where(Doctor.department_id == department_id)
    if specialization:
        stmt = stmt.where(Doctor.specialization.ilike(like_term(specialization), escape="\\"))
    if search:
        term = like_term(search)
        stmt = stmt.where(
            or_(
                Doctor.first_name.ilike(term, escape="\\"),
                Doctor.last_name.ilike(term, escape="\\"),
                Doctor.specialization.ilike(term, escape="\\"),
                Doctor.license_number.ilike(term, escape="\\"),
            )
        )
    return paginate(db, stmt, page, page_size)


def _validate_blocks(blocks: list[ScheduleBlock]) -> None:
    by_day: dict[int, list[ScheduleBlock]] = defaultdict(list)
    for block in blocks:
        by_day[block.day_of_week].append(block)
    for day_blocks in by_day.values():
        day_blocks.sort(key=lambda b: b.start_time)
        for prev, cur in zip(day_blocks, day_blocks[1:], strict=False):
            if cur.start_time < prev.end_time:
                raise BusinessRuleError("Schedule blocks on the same day must not overlap")


def _check_department(db: Session, department_id: int) -> None:
    dept = db.get(Department, department_id)
    if dept is None or not dept.is_active:
        raise BusinessRuleError("Department does not exist or is inactive")


def _check_user_link(db: Session, user_id: int, doctor_id: int | None = None) -> None:
    user = db.get(User, user_id)
    if user is None or user.role != Role.DOCTOR:
        raise BusinessRuleError("Linked user must exist and have the doctor role")
    linked = db.scalar(select(Doctor.id).where(Doctor.user_id == user_id))
    if linked and linked != doctor_id:
        raise ConflictError("This user account is already linked to another doctor")


def _check_unique(
    db: Session, *, license_number: str | None, email: str | None, exclude_id: int | None = None
) -> None:
    conditions = []
    if license_number:
        conditions.append(Doctor.license_number == license_number)
    if email:
        conditions.append(Doctor.email == email.lower())
    if not conditions:
        return
    stmt = select(Doctor.id).where(or_(*conditions))
    if exclude_id:
        stmt = stmt.where(Doctor.id != exclude_id)
    if db.scalar(stmt):
        raise ConflictError("A doctor with this licence number or e-mail already exists")


def create_doctor(db: Session, data: DoctorCreate) -> Doctor:
    _check_department(db, data.department_id)
    _check_unique(db, license_number=data.license_number, email=data.email)
    if data.user_id:
        _check_user_link(db, data.user_id)
    _validate_blocks(data.schedules)
    fields = data.model_dump(exclude={"schedules"})
    fields["email"] = fields["email"].lower()
    doctor = Doctor(**fields)
    doctor.schedules = [DoctorSchedule(**b.model_dump()) for b in data.schedules]
    db.add(doctor)
    db.commit()
    return doctor


def update_doctor(db: Session, doctor: Doctor, data: DoctorUpdate) -> Doctor:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("department_id"):
        _check_department(db, changes["department_id"])
    if changes.get("email"):
        changes["email"] = changes["email"].lower()
        _check_unique(db, license_number=None, email=changes["email"], exclude_id=doctor.id)
    if changes.get("user_id"):
        _check_user_link(db, changes["user_id"], doctor.id)
    for key, value in changes.items():
        if value is not None or key == "user_id":
            setattr(doctor, key, value)
    db.commit()
    return doctor


def deactivate_doctor(db: Session, doctor: Doctor) -> Doctor:
    """Doctors are never hard-deleted so appointment/prescription history stays intact."""
    doctor.is_active = False
    db.commit()
    return doctor


def replace_schedules(db: Session, doctor: Doctor, blocks: list[ScheduleBlock]) -> Doctor:
    _validate_blocks(blocks)
    doctor.schedules.clear()
    db.flush()  # delete old rows first so re-used (day, start_time) pairs don't collide
    doctor.schedules.extend(DoctorSchedule(**b.model_dump()) for b in blocks)
    db.commit()
    db.refresh(doctor)
    return doctor


def active_appointments_between(
    db: Session, doctor_id: int, start: datetime, end: datetime
) -> list[Appointment]:
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.scheduled_at >= start - timedelta(hours=4),
        Appointment.scheduled_at < end,
    )
    return list(db.scalars(stmt))


def availability(db: Session, doctor: Doctor, day: date) -> list[dict]:
    """Bookable slots for a calendar day (hospital-local), marking taken / past slots."""
    if not doctor.is_active:
        raise NotFoundError("Doctor is not active")
    tz = hospital_tz()
    blocks = [b for b in doctor.schedules if b.day_of_week == day.weekday()]
    day_start, day_end = local_day_bounds(day)
    booked = [
        (a.scheduled_at, a.scheduled_at + timedelta(minutes=a.duration_minutes))
        for a in active_appointments_between(db, doctor.id, day_start, day_end)
    ]
    now = now_utc()
    slots: list[dict] = []
    for block in sorted(blocks, key=lambda b: b.start_time):
        cursor = datetime.combine(day, block.start_time, tzinfo=tz)
        block_end = datetime.combine(day, block.end_time, tzinfo=tz)
        step = timedelta(minutes=block.slot_minutes)
        while cursor + step <= block_end:
            slot_end = cursor + step
            taken = any(start < slot_end and end > cursor for start, end in booked)
            slots.append(
                {"start": cursor, "end": slot_end, "available": not taken and cursor > now}
            )
            cursor = slot_end
    return slots
