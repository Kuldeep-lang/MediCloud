"""Dashboard aggregations. Everything is computed live from the database."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.orm import Session

from app.core.timeutils import hospital_tz, local_day_bounds, local_month_start, local_today
from app.models import (
    Admission,
    Appointment,
    Bed,
    Department,
    Doctor,
    Invoice,
    Medicine,
    Patient,
    Payment,
    Prescription,
    Ward,
)
from app.models.enums import (
    AdmissionStatus,
    AppointmentStatus,
    BedStatus,
    InvoiceStatus,
    PaymentStatus,
    PrescriptionStatus,
    WardType,
)


def _local_date(column):
    """Calendar date of a timestamptz column in hospital-local time (labelled 'day')."""
    return cast(func.timezone(str(hospital_tz()), column), Date).label("day")


def _bed_stats(db: Session, ward_type: WardType | None = None) -> dict[str, int]:
    stmt = select(Bed.status, func.count()).group_by(Bed.status)
    if ward_type:
        stmt = stmt.join(Ward, Ward.id == Bed.ward_id).where(Ward.ward_type == ward_type)
    counts = {status.value: count for status, count in db.execute(stmt).all()}
    stats = {s.value: counts.get(s.value, 0) for s in BedStatus}
    return {"total": sum(stats.values()), **stats}


def appointments_on(db: Session, day: date, doctor_id: int | None = None) -> int:
    start, end = local_day_bounds(day)
    stmt = select(func.count(Appointment.id)).where(
        Appointment.scheduled_at >= start,
        Appointment.scheduled_at < end,
        Appointment.status != AppointmentStatus.CANCELLED,
    )
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    return db.scalar(stmt) or 0


def monthly_revenue(db: Session) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.SUCCESS, Payment.paid_at >= local_month_start()
        )
    ) or Decimal("0")


def summary(
    db: Session, *, include_revenue: bool, include_billing: bool, doctor_id: int | None
) -> dict:
    today = local_today()
    data = {
        "total_patients": db.scalar(select(func.count(Patient.id))) or 0,
        "total_doctors": db.scalar(select(func.count(Doctor.id)).where(Doctor.is_active.is_(True)))
        or 0,
        "appointments_today": appointments_on(db, today),
        "beds": _bed_stats(db),
        "icu": _bed_stats(db, WardType.ICU),
        "active_admissions": db.scalar(
            select(func.count(Admission.id)).where(Admission.status == AdmissionStatus.ADMITTED)
        )
        or 0,
        "pending_prescriptions": db.scalar(
            select(func.count(Prescription.id)).where(
                Prescription.status == PrescriptionStatus.PENDING
            )
        )
        or 0,
        "low_stock_medicines": db.scalar(
            select(func.count(Medicine.id)).where(
                Medicine.is_active.is_(True), Medicine.stock_quantity <= Medicine.reorder_level
            )
        )
        or 0,
    }
    if doctor_id:
        data["my_appointments_today"] = appointments_on(db, today, doctor_id)
    if include_billing:
        data["unpaid_invoices"] = (
            db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID])
                )
            )
            or 0
        )
    if include_revenue:
        data["monthly_revenue"] = monthly_revenue(db)
    return data


def _day_range(days: int) -> list[date]:
    today = local_today()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def admissions_trend(db: Session, days: int) -> list[dict]:
    span = _day_range(days)
    start, _ = local_day_bounds(span[0])

    def per_day(column, *conditions) -> dict[date, int]:
        day = _local_date(column)
        rows = db.execute(
            select(day, func.count()).where(column >= start, *conditions).group_by("day")
        ).all()
        return dict(rows)

    admitted = per_day(Admission.admitted_at)
    discharged = per_day(Admission.discharged_at, Admission.discharged_at.is_not(None))
    return [
        {"date": d, "admissions": admitted.get(d, 0), "discharges": discharged.get(d, 0)}
        for d in span
    ]


def appointment_stats(db: Session, days: int) -> dict:
    span = _day_range(days)
    start, _ = local_day_bounds(span[0])
    _, end = local_day_bounds(span[-1])
    window = (Appointment.scheduled_at >= start, Appointment.scheduled_at < end)

    by_status = db.execute(
        select(Appointment.status, func.count()).where(*window).group_by(Appointment.status)
    ).all()
    status_counts = {s.value: 0 for s in AppointmentStatus}
    status_counts.update({status.value: count for status, count in by_status})

    day = _local_date(Appointment.scheduled_at)
    rows = db.execute(
        select(day, Appointment.status, func.count())
        .where(*window)
        .group_by("day", Appointment.status)
    ).all()
    daily: dict[date, dict[str, int]] = {
        d: {"total": 0, "completed": 0, "cancelled": 0} for d in span
    }
    for d, status, count in rows:
        bucket = daily.setdefault(d, {"total": 0, "completed": 0, "cancelled": 0})
        bucket["total"] += count
        if status == AppointmentStatus.COMPLETED:
            bucket["completed"] += count
        elif status == AppointmentStatus.CANCELLED:
            bucket["cancelled"] += count
    return {
        "by_status": [{"status": k, "count": v} for k, v in status_counts.items()],
        "daily": [{"date": d, **daily[d]} for d in span],
    }


def department_distribution(db: Session, days: int) -> list[dict]:
    start, _ = local_day_bounds(local_today() - timedelta(days=days - 1))
    rows = db.execute(
        select(Department.name, func.count(distinct(Appointment.patient_id)))
        .join(Doctor, Doctor.department_id == Department.id)
        .join(Appointment, Appointment.doctor_id == Doctor.id)
        .where(
            Appointment.scheduled_at >= start,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
        .group_by(Department.name)
        .order_by(func.count(distinct(Appointment.patient_id)).desc())
    ).all()
    return [{"department": name, "patients": count} for name, count in rows]


def revenue_by_month(db: Session, months: int) -> list[dict]:
    today = local_today()
    # First day of the earliest month in the window.
    year, month = today.year, today.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    start = local_month_start(date(year, month, 1))
    month_col = func.to_char(func.timezone(str(hospital_tz()), Payment.paid_at), "YYYY-MM")
    rows = dict(
        db.execute(
            select(month_col.label("month"), func.sum(Payment.amount))
            .where(Payment.status == PaymentStatus.SUCCESS, Payment.paid_at >= start)
            .group_by("month")
        ).all()
    )
    result = []
    y, m = year, month
    for _ in range(months):
        key = f"{y:04d}-{m:02d}"
        result.append({"month": key, "revenue": rows.get(key, Decimal("0"))})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result
