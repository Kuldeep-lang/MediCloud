from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import PrescriptionStatus, StockReason
from app.schemas.common import LongText, Money, MoneyIn, ORMModel, ShortText

MedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
MedCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9\-]{2,20}$")
]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Tiny = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
Text120 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Batch = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]


# ---------------- Medicines ----------------
class MedicineCreate(BaseModel):
    code: MedCode
    name: MedName
    generic_name: Text120 | None = None
    category: Short | None = None
    manufacturer: Text120 | None = None
    dosage_form: Tiny | None = None
    strength: Tiny | None = None
    unit_price: MoneyIn
    stock_quantity: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    reorder_level: Annotated[int, Field(ge=0, le=100_000)] = 10
    batch_number: Batch | None = None
    expiry_date: date


class MedicineUpdate(BaseModel):
    """Stock quantity is NOT editable here - use the stock adjustment endpoint (ledger)."""

    name: MedName | None = None
    generic_name: Text120 | None = None
    category: Short | None = None
    manufacturer: Text120 | None = None
    dosage_form: Tiny | None = None
    strength: Tiny | None = None
    unit_price: MoneyIn | None = None
    reorder_level: Annotated[int, Field(ge=0, le=100_000)] | None = None
    batch_number: Batch | None = None
    expiry_date: date | None = None
    is_active: bool | None = None


class MedicineOut(ORMModel):
    id: int
    code: str
    name: str
    generic_name: str | None
    category: str | None
    manufacturer: str | None
    dosage_form: str | None
    strength: str | None
    unit_price: Money
    stock_quantity: int
    reorder_level: int
    batch_number: str | None
    expiry_date: date
    is_active: bool
    is_low_stock: bool
    is_expired: bool
    days_to_expiry: int


class StockAdjustment(BaseModel):
    change_quantity: Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
    reason: Literal["restock", "adjustment", "expired"]
    reference: Short | None = None


class StockMovementOut(ORMModel):
    id: int
    medicine_id: int
    medicine_name: str
    change_quantity: int
    balance_after: int
    reason: StockReason
    reference: str | None
    performed_by: int | None
    created_at: datetime


class MedicineAlerts(BaseModel):
    low_stock: list[MedicineOut]
    expiring_soon: list[MedicineOut]
    expired: list[MedicineOut]


class UsagePoint(BaseModel):
    date: date
    quantity: int


class TopMedicine(BaseModel):
    medicine_id: int
    name: str
    quantity: int


class StockUsage(BaseModel):
    daily: list[UsagePoint]
    top_medicines: list[TopMedicine]


# ---------------- Prescriptions ----------------
class PrescriptionItemIn(BaseModel):
    medicine_id: int
    dosage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    frequency: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    duration_days: Annotated[int, Field(ge=1, le=365)] | None = None
    quantity: Annotated[int, Field(ge=1, le=10_000)]
    instructions: ShortText | None = None


class PrescriptionCreate(BaseModel):
    patient_id: int
    doctor_id: int | None = Field(
        default=None, description="Required for admins; doctors always prescribe as themselves"
    )
    appointment_id: int | None = None
    notes: LongText | None = None
    items: Annotated[list[PrescriptionItemIn], Field(min_length=1, max_length=20)]


class PrescriptionItemOut(ORMModel):
    id: int
    medicine_id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration_days: int | None
    quantity: int
    instructions: str | None
    unit_price: Money


class PrescriptionOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    appointment_id: int | None
    status: PrescriptionStatus
    notes: str | None
    dispensed_at: datetime | None
    created_at: datetime
    items: list[PrescriptionItemOut]
