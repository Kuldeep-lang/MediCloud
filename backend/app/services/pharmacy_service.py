from datetime import timedelta

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.timeutils import hospital_tz, local_day_bounds, local_today, now_utc
from app.models import (
    Appointment,
    Medicine,
    Patient,
    Prescription,
    PrescriptionItem,
    StockMovement,
    User,
)
from app.models.enums import PrescriptionStatus, Role, StockReason
from app.schemas.pharmacy import (
    MedicineCreate,
    MedicineUpdate,
    PrescriptionCreate,
    StockAdjustment,
)
from app.services.common import get_or_404, like_term, paginate


# ---------------- Medicines ----------------
def list_medicines(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    low_stock: bool,
    expiring_within_days: int | None,
    include_inactive: bool,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Medicine).order_by(Medicine.name)
    if not include_inactive:
        stmt = stmt.where(Medicine.is_active.is_(True))
    if search:
        term = like_term(search)
        stmt = stmt.where(
            or_(
                Medicine.name.ilike(term, escape="\\"),
                Medicine.generic_name.ilike(term, escape="\\"),
                Medicine.code.ilike(term, escape="\\"),
                Medicine.category.ilike(term, escape="\\"),
            )
        )
    if category:
        stmt = stmt.where(Medicine.category == category)
    if low_stock:
        stmt = stmt.where(Medicine.stock_quantity <= Medicine.reorder_level)
    if expiring_within_days is not None:
        stmt = stmt.where(
            Medicine.expiry_date <= local_today() + timedelta(days=expiring_within_days)
        )
    return paginate(db, stmt, page, page_size)


def list_categories(db: Session) -> list[str]:
    rows = db.scalars(
        select(Medicine.category).where(Medicine.category.is_not(None)).distinct()
    ).all()
    return sorted(rows)


def create_medicine(db: Session, data: MedicineCreate, user: User) -> Medicine:
    if db.scalar(select(Medicine.id).where(Medicine.code == data.code)):
        raise ConflictError("A medicine with this code already exists")
    medicine = Medicine(**data.model_dump())
    db.add(medicine)
    db.flush()
    if medicine.stock_quantity > 0:
        db.add(
            StockMovement(
                medicine_id=medicine.id,
                change_quantity=medicine.stock_quantity,
                balance_after=medicine.stock_quantity,
                reason=StockReason.RESTOCK,
                reference="initial stock",
                performed_by=user.id,
            )
        )
    db.commit()
    return medicine


def update_medicine(db: Session, medicine: Medicine, data: MedicineUpdate) -> Medicine:
    for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(medicine, key, value)
    db.commit()
    return medicine


def deactivate_medicine(db: Session, medicine: Medicine) -> Medicine:
    medicine.is_active = False
    db.commit()
    return medicine


def _lock_medicines(db: Session, ids: list[int]) -> dict[int, Medicine]:
    """Lock rows in a consistent (id) order to avoid deadlocks between transactions."""
    rows = db.scalars(
        select(Medicine)
        .where(Medicine.id.in_(ids))
        .order_by(Medicine.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {m.id: m for m in rows}


def adjust_stock(db: Session, medicine_id: int, data: StockAdjustment, user: User) -> Medicine:
    medicine = _lock_medicines(db, [medicine_id]).get(medicine_id)
    if medicine is None:
        raise NotFoundError(f"Medicine {medicine_id} not found")
    if data.change_quantity == 0:
        raise BusinessRuleError("Change quantity must not be zero")
    if data.reason == "restock" and data.change_quantity < 0:
        raise BusinessRuleError("A restock must add stock (positive quantity)")
    if data.reason == "expired" and data.change_quantity > 0:
        raise BusinessRuleError("An expiry write-off must remove stock (negative quantity)")
    new_balance = medicine.stock_quantity + data.change_quantity
    if new_balance < 0:
        raise BusinessRuleError(
            f"Insufficient stock: {medicine.stock_quantity} available, "
            f"{-data.change_quantity} requested"
        )
    medicine.stock_quantity = new_balance
    db.add(
        StockMovement(
            medicine_id=medicine.id,
            change_quantity=data.change_quantity,
            balance_after=new_balance,
            reason=StockReason(data.reason),
            reference=data.reference,
            performed_by=user.id,
        )
    )
    db.commit()
    return medicine


def list_movements(db: Session, medicine_id: int, page: int, page_size: int) -> dict:
    get_or_404(db, Medicine, medicine_id, "Medicine")
    stmt = (
        select(StockMovement)
        .where(StockMovement.medicine_id == medicine_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )
    return paginate(db, stmt, page, page_size)


def alerts(db: Session, expiring_within_days: int = 30) -> dict:
    today = local_today()
    active = select(Medicine).where(Medicine.is_active.is_(True)).order_by(Medicine.name)
    low = db.scalars(active.where(Medicine.stock_quantity <= Medicine.reorder_level)).all()
    expiring = db.scalars(
        active.where(
            Medicine.expiry_date >= today,
            Medicine.expiry_date <= today + timedelta(days=expiring_within_days),
        )
    ).all()
    expired = db.scalars(
        active.where(Medicine.expiry_date < today, Medicine.stock_quantity > 0)
    ).all()
    return {"low_stock": list(low), "expiring_soon": list(expiring), "expired": list(expired)}


def stock_usage(db: Session, days: int = 30) -> dict:
    """Daily dispensed quantities (zero-filled) and the top dispensed medicines."""
    today = local_today()
    first_day = today - timedelta(days=days - 1)
    start, _ = local_day_bounds(first_day)
    day_col = cast(func.timezone(str(hospital_tz()), StockMovement.created_at), Date).label("day")
    dispensed = func.sum(-StockMovement.change_quantity)
    conditions = (
        StockMovement.reason == StockReason.DISPENSE,
        StockMovement.created_at >= start,
    )
    # Group by the label: repeating an expression with a bound parameter in GROUP BY fails.
    daily_rows = dict(
        db.execute(select(day_col, dispensed).where(*conditions).group_by("day")).all()
    )
    daily = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        daily.append({"date": day, "quantity": int(daily_rows.get(day, 0))})
    top_rows = db.execute(
        select(StockMovement.medicine_id, Medicine.name, dispensed)
        .join(Medicine, Medicine.id == StockMovement.medicine_id)
        .where(*conditions)
        .group_by(StockMovement.medicine_id, Medicine.name)
        .order_by(dispensed.desc())
        .limit(5)
    ).all()
    top = [{"medicine_id": mid, "name": name, "quantity": int(qty)} for mid, name, qty in top_rows]
    return {"daily": daily, "top_medicines": top}


# ---------------- Prescriptions ----------------
def list_prescriptions(
    db: Session,
    *,
    status: PrescriptionStatus | None,
    patient_id: int | None,
    doctor_id: int | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Prescription).order_by(Prescription.created_at.desc(), Prescription.id.desc())
    if status:
        stmt = stmt.where(Prescription.status == status)
    if patient_id:
        stmt = stmt.where(Prescription.patient_id == patient_id)
    if doctor_id:
        stmt = stmt.where(Prescription.doctor_id == doctor_id)
    return paginate(db, stmt, page, page_size)


def create_prescription(db: Session, data: PrescriptionCreate, user: User) -> Prescription:
    if user.role == Role.DOCTOR:
        if user.doctor_id is None:
            raise BusinessRuleError("Your account is not linked to a doctor profile")
        doctor_id = user.doctor_id
    else:
        if data.doctor_id is None:
            raise BusinessRuleError("doctor_id is required")
        doctor_id = data.doctor_id
    get_or_404(db, Patient, data.patient_id, "Patient")
    if data.appointment_id:
        appt = get_or_404(db, Appointment, data.appointment_id, "Appointment")
        if appt.patient_id != data.patient_id or appt.doctor_id != doctor_id:
            raise BusinessRuleError("The appointment does not belong to this patient and doctor")

    medicine_ids = [item.medicine_id for item in data.items]
    if len(set(medicine_ids)) != len(medicine_ids):
        raise BusinessRuleError("Each medicine may appear only once per prescription")
    medicines = {m.id: m for m in db.scalars(select(Medicine).where(Medicine.id.in_(medicine_ids)))}
    for mid in medicine_ids:
        med = medicines.get(mid)
        if med is None or not med.is_active:
            raise BusinessRuleError(f"Medicine {mid} does not exist or is inactive")

    prescription = Prescription(
        patient_id=data.patient_id,
        doctor_id=doctor_id,
        appointment_id=data.appointment_id,
        notes=data.notes,
        items=[PrescriptionItem(**item.model_dump()) for item in data.items],
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def _lock_prescription(db: Session, prescription_id: int) -> Prescription:
    prescription = db.scalar(
        select(Prescription)
        .where(Prescription.id == prescription_id)
        .with_for_update(of=Prescription)
        .execution_options(populate_existing=True)
    )
    if prescription is None:
        raise NotFoundError(f"Prescription {prescription_id} not found")
    return prescription


def dispense_prescription(db: Session, prescription_id: int, user: User) -> Prescription:
    """Atomically decrement stock for every item and write ledger entries.

    Either every item is dispensed or nothing changes (single transaction).
    """
    prescription = _lock_prescription(db, prescription_id)
    if prescription.status != PrescriptionStatus.PENDING:
        raise BusinessRuleError(f"Prescription is already {prescription.status.value}")
    medicines = _lock_medicines(db, sorted(i.medicine_id for i in prescription.items))

    problems = []
    for item in prescription.items:
        med = medicines[item.medicine_id]
        if med.is_expired:
            problems.append(f"{med.name} is expired")
        elif med.stock_quantity < item.quantity:
            problems.append(f"{med.name}: {med.stock_quantity} in stock, {item.quantity} needed")
    if problems:
        raise BusinessRuleError("Cannot dispense - " + "; ".join(problems))

    for item in prescription.items:
        med = medicines[item.medicine_id]
        med.stock_quantity -= item.quantity
        db.add(
            StockMovement(
                medicine_id=med.id,
                change_quantity=-item.quantity,
                balance_after=med.stock_quantity,
                reason=StockReason.DISPENSE,
                reference=f"prescription:{prescription.id}",
                performed_by=user.id,
            )
        )
    prescription.status = PrescriptionStatus.DISPENSED
    prescription.dispensed_at = now_utc()
    prescription.dispensed_by = user.id
    db.commit()
    db.refresh(prescription)
    return prescription


def cancel_prescription(db: Session, prescription_id: int) -> Prescription:
    prescription = _lock_prescription(db, prescription_id)
    if prescription.status != PrescriptionStatus.PENDING:
        raise BusinessRuleError(f"Prescription is already {prescription.status.value}")
    prescription.status = PrescriptionStatus.CANCELLED
    db.commit()
    return prescription
