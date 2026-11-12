from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import InvoiceItemType, InvoiceStatus, PaymentMethod, PaymentStatus
from app.schemas.common import Money, MoneyIn, ORMModel, ShortText

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class InvoiceItemIn(BaseModel):
    item_type: InvoiceItemType
    description: Description
    quantity: Annotated[int, Field(ge=1, le=10_000)] = 1
    unit_price: MoneyIn
    appointment_id: int | None = None
    prescription_item_id: int | None = None
    admission_id: int | None = None


class InvoiceCreate(BaseModel):
    patient_id: int
    admission_id: int | None = None
    items: Annotated[list[InvoiceItemIn], Field(min_length=1, max_length=100)]
    discount: MoneyIn = Decimal("0")
    tax_percent: Percent = Decimal("0")
    due_date: date | None = None
    notes: ShortText | None = None


class InvoiceGenerate(BaseModel):
    """Build an invoice automatically from everything billable for the patient."""

    patient_id: int
    include_consultations: bool = True
    include_medicines: bool = True
    include_room: bool = True
    extra_items: Annotated[list[InvoiceItemIn], Field(max_length=50)] = []
    discount: MoneyIn = Decimal("0")
    tax_percent: Percent = Decimal("0")
    due_date: date | None = None
    notes: ShortText | None = None


class BillableItem(BaseModel):
    item_type: InvoiceItemType
    description: str
    quantity: int
    unit_price: Money
    line_total: Money
    appointment_id: int | None = None
    prescription_item_id: int | None = None
    admission_id: int | None = None


class BillableSummary(BaseModel):
    patient_id: int
    items: list[BillableItem]
    subtotal: Money


class InvoiceItemOut(ORMModel):
    id: int
    item_type: InvoiceItemType
    description: str
    quantity: int
    unit_price: Money
    line_total: Money
    appointment_id: int | None
    prescription_item_id: int | None


class PaymentCreate(BaseModel):
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    method: PaymentMethod
    simulate_failure: bool = Field(
        default=False, description="Simulation only: record a declined payment"
    )


class PaymentOut(ORMModel):
    id: int
    invoice_id: int
    amount: Money
    method: PaymentMethod
    status: PaymentStatus
    transaction_ref: str
    paid_at: datetime


class PaymentListItem(PaymentOut):
    invoice_number: str
    patient_name: str


class InvoiceOut(ORMModel):
    id: int
    invoice_number: str
    patient_id: int
    patient_name: str
    patient_code: str
    admission_id: int | None
    issued_at: datetime
    due_date: date | None
    subtotal: Money
    discount: Money
    tax: Money
    total: Money
    amount_paid: Money
    balance_due: Money
    status: InvoiceStatus
    notes: str | None


class InvoiceDetail(InvoiceOut):
    items: list[InvoiceItemOut]
    payments: list[PaymentOut]
