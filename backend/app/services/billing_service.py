"""Billing: invoices built from consultations, dispensed medicines and room stays.

Payments are SIMULATED - no payment gateway is ever contacted.
"""

import math
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.timeutils import hospital_tz, now_utc
from app.models import (
    Admission,
    Appointment,
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    Prescription,
    PrescriptionItem,
    User,
)
from app.models.enums import (
    AppointmentStatus,
    InvoiceItemType,
    InvoiceStatus,
    PaymentStatus,
    PrescriptionStatus,
)
from app.schemas.billing import InvoiceCreate, InvoiceGenerate, InvoiceItemIn, PaymentCreate
from app.services.common import get_or_404, like_term, paginate

CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _billed_ids(db: Session, patient_id: int, column) -> set[int]:
    """Source ids already present on a non-cancelled invoice for this patient."""
    rows = db.scalars(
        select(column)
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(
            Invoice.patient_id == patient_id,
            Invoice.status != InvoiceStatus.CANCELLED,
            column.is_not(None),
        )
    ).all()
    return set(rows)


def billable_items(db: Session, patient_id: int) -> list[dict]:
    get_or_404(db, Patient, patient_id, "Patient")
    tz = hospital_tz()
    items: list[dict] = []

    billed_appts = _billed_ids(db, patient_id, InvoiceItem.appointment_id)
    for appt in db.scalars(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        .order_by(Appointment.scheduled_at)
    ):
        if appt.id in billed_appts:
            continue
        fee = appt.doctor.consultation_fee
        when = appt.scheduled_at.astimezone(tz).strftime("%d %b %Y")
        items.append(
            {
                "item_type": InvoiceItemType.CONSULTATION,
                "description": f"Consultation - {appt.doctor.full_name} "
                f"({appt.doctor.department.name}), {when}",
                "quantity": 1,
                "unit_price": fee,
                "line_total": fee,
                "appointment_id": appt.id,
            }
        )

    billed_rx_items = _billed_ids(db, patient_id, InvoiceItem.prescription_item_id)
    for item in db.scalars(
        select(PrescriptionItem)
        .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
        .where(
            Prescription.patient_id == patient_id,
            Prescription.status == PrescriptionStatus.DISPENSED,
        )
        .order_by(PrescriptionItem.id)
    ):
        if item.id in billed_rx_items:
            continue
        price = item.medicine.unit_price
        items.append(
            {
                "item_type": InvoiceItemType.MEDICINE,
                "description": f"{item.medicine.name} ({item.dosage}) x {item.quantity}",
                "quantity": item.quantity,
                "unit_price": price,
                "line_total": _money(price * item.quantity),
                "prescription_item_id": item.id,
            }
        )

    billed_admissions = _billed_ids(db, patient_id, InvoiceItem.admission_id)
    now = now_utc()
    for adm in db.scalars(
        select(Admission).where(Admission.patient_id == patient_id).order_by(Admission.admitted_at)
    ):
        if adm.id in billed_admissions:
            continue
        end = adm.discharged_at or now
        days = max(1, math.ceil((end - adm.admitted_at).total_seconds() / 86400))
        rate = adm.bed.ward.daily_rate
        status = "" if adm.discharged_at else " - ongoing"
        items.append(
            {
                "item_type": InvoiceItemType.ROOM,
                "description": f"Room charges - {adm.bed.ward.name}, bed {adm.bed.bed_number} "
                f"({days} day{'s' if days > 1 else ''}{status})",
                "quantity": days,
                "unit_price": rate,
                "line_total": _money(rate * days),
                "admission_id": adm.id,
            }
        )
    return items


def _validate_sources(db: Session, patient_id: int, items: list[InvoiceItemIn]) -> None:
    billed_appts = _billed_ids(db, patient_id, InvoiceItem.appointment_id)
    billed_rx = _billed_ids(db, patient_id, InvoiceItem.prescription_item_id)
    billed_admissions = _billed_ids(db, patient_id, InvoiceItem.admission_id)
    for item in items:
        if item.admission_id is not None:
            adm = db.get(Admission, item.admission_id)
            if adm is None or adm.patient_id != patient_id:
                raise BusinessRuleError(f"Admission {item.admission_id} is not this patient's")
            if item.admission_id in billed_admissions:
                raise BusinessRuleError(
                    f"Room charges for admission {item.admission_id} are billed"
                )
        if item.appointment_id is not None:
            appt = db.get(Appointment, item.appointment_id)
            if appt is None or appt.patient_id != patient_id:
                raise BusinessRuleError(f"Appointment {item.appointment_id} is not this patient's")
            if item.appointment_id in billed_appts:
                raise BusinessRuleError(f"Appointment {item.appointment_id} is already billed")
        if item.prescription_item_id is not None:
            rx_item = db.get(PrescriptionItem, item.prescription_item_id)
            if rx_item is None or rx_item.prescription.patient_id != patient_id:
                raise BusinessRuleError(
                    f"Prescription item {item.prescription_item_id} is not this patient's"
                )
            if item.prescription_item_id in billed_rx:
                raise BusinessRuleError(
                    f"Prescription item {item.prescription_item_id} is already billed"
                )


def _build_invoice(
    db: Session,
    *,
    patient_id: int,
    items: list[dict],
    discount: Decimal,
    tax_percent: Decimal,
    due_date,
    notes: str | None,
    user: User,
) -> Invoice:
    subtotal = _money(sum((Decimal(i["unit_price"]) * i["quantity"] for i in items), Decimal(0)))
    if discount > subtotal:
        raise BusinessRuleError("Discount cannot exceed the subtotal")
    tax = _money((subtotal - discount) * tax_percent / 100)
    total = _money(subtotal - discount + tax)
    admission_ids = {i.get("admission_id") for i in items if i.get("admission_id")}
    invoice = Invoice(
        patient_id=patient_id,
        admission_id=admission_ids.pop() if len(admission_ids) == 1 else None,
        subtotal=subtotal,
        discount=_money(discount),
        tax=tax,
        total=total,
        due_date=due_date,
        notes=notes,
        status=InvoiceStatus.PAID if total == 0 else InvoiceStatus.UNPAID,
        created_by=user.id,
        items=[
            InvoiceItem(
                item_type=i["item_type"],
                description=i["description"],
                quantity=i["quantity"],
                unit_price=_money(Decimal(i["unit_price"])),
                appointment_id=i.get("appointment_id"),
                prescription_item_id=i.get("prescription_item_id"),
                admission_id=i.get("admission_id"),
            )
            for i in items
        ],
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_invoice(db: Session, data: InvoiceCreate, user: User) -> Invoice:
    get_or_404(db, Patient, data.patient_id, "Patient")
    if data.admission_id:
        adm = get_or_404(db, Admission, data.admission_id, "Admission")
        if adm.patient_id != data.patient_id:
            raise BusinessRuleError("The admission does not belong to this patient")
    _validate_sources(db, data.patient_id, data.items)
    items = [i.model_dump() for i in data.items]
    if data.admission_id:
        for item in items:
            if item["item_type"] == InvoiceItemType.ROOM:
                item["admission_id"] = data.admission_id
    return _build_invoice(
        db,
        patient_id=data.patient_id,
        items=items,
        discount=data.discount,
        tax_percent=data.tax_percent,
        due_date=data.due_date,
        notes=data.notes,
        user=user,
    )


def generate_invoice(db: Session, data: InvoiceGenerate, user: User) -> Invoice:
    wanted = {
        InvoiceItemType.CONSULTATION: data.include_consultations,
        InvoiceItemType.MEDICINE: data.include_medicines,
        InvoiceItemType.ROOM: data.include_room,
    }
    items = [i for i in billable_items(db, data.patient_id) if wanted.get(i["item_type"], True)]
    items += [i.model_dump() for i in data.extra_items]
    if not items:
        raise BusinessRuleError("There is nothing to bill for this patient")
    return _build_invoice(
        db,
        patient_id=data.patient_id,
        items=items,
        discount=data.discount,
        tax_percent=data.tax_percent,
        due_date=data.due_date,
        notes=data.notes,
        user=user,
    )


def list_invoices(
    db: Session,
    *,
    patient_id: int | None,
    status: InvoiceStatus | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Invoice).order_by(Invoice.issued_at.desc(), Invoice.id.desc())
    if patient_id:
        stmt = stmt.where(Invoice.patient_id == patient_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if search:
        term = like_term(search)
        stmt = stmt.join(Invoice.patient.of_type(Patient)).where(
            or_(
                Invoice.invoice_number.ilike(term, escape="\\"),
                Patient.first_name.ilike(term, escape="\\"),
                Patient.last_name.ilike(term, escape="\\"),
                Patient.patient_code.ilike(term, escape="\\"),
            )
        )
    return paginate(db, stmt, page, page_size)


def _lock_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update(of=Invoice)
        .execution_options(populate_existing=True)
    )
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")
    return invoice


def cancel_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = _lock_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.CANCELLED:
        raise BusinessRuleError("Invoice is already cancelled")
    if invoice.amount_paid > 0:
        raise BusinessRuleError("An invoice with successful payments cannot be cancelled")
    invoice.status = InvoiceStatus.CANCELLED
    db.commit()
    return invoice


def record_payment(db: Session, invoice_id: int, data: PaymentCreate, user: User) -> Payment:
    """Record a SIMULATED payment. Row lock prevents concurrent over-payment."""
    invoice = _lock_invoice(db, invoice_id)
    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.PAID):
        raise BusinessRuleError(f"Invoice is {invoice.status.value}; no payment is due")
    if data.amount > invoice.balance_due:
        raise BusinessRuleError(f"Amount exceeds the balance due ({invoice.balance_due})")
    payment = Payment(
        amount=_money(data.amount),
        method=data.method,
        status=PaymentStatus.FAILED if data.simulate_failure else PaymentStatus.SUCCESS,
        transaction_ref=f"SIM-{uuid.uuid4().hex[:16].upper()}",
        paid_at=now_utc(),
        received_by=user.id,
    )
    invoice.payments.append(payment)
    if payment.status == PaymentStatus.SUCCESS:
        invoice.status = (
            InvoiceStatus.PAID
            if invoice.amount_paid >= invoice.total
            else InvoiceStatus.PARTIALLY_PAID
        )
    db.commit()
    return payment


def list_payments(db: Session, *, invoice_id: int | None, page: int, page_size: int) -> dict:
    stmt = select(Payment).order_by(Payment.paid_at.desc(), Payment.id.desc())
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    return paginate(db, stmt, page, page_size)
