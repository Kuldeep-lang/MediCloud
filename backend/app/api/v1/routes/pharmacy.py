"""Medicines (inventory, stock ledger, alerts) and prescriptions (create / dispense)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import (
    DbSession,
    Paging,
    PharmacyUser,
    PrescriberUser,
    require_roles,
    scoped_doctor_id,
)
from app.models import Medicine, Prescription, User
from app.models.enums import PrescriptionStatus, Role
from app.schemas.common import Page
from app.schemas.pharmacy import (
    MedicineAlerts,
    MedicineCreate,
    MedicineOut,
    MedicineUpdate,
    PrescriptionCreate,
    PrescriptionOut,
    StockAdjustment,
    StockMovementOut,
    StockUsage,
)
from app.services import pharmacy_service
from app.services.common import get_or_404

router = APIRouter(tags=["pharmacy"])

# Doctors can read the formulary to prescribe; only pharmacy staff change it.
MedicineReader = Annotated[User, Depends(require_roles(Role.ADMIN, Role.PHARMACIST, Role.DOCTOR))]
PrescriptionReader = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.DOCTOR, Role.PHARMACIST, Role.RECEPTIONIST))
]


# ---------------- Medicines ----------------
@router.get("/medicines", response_model=Page[MedicineOut])
def list_medicines(
    _: MedicineReader,
    db: DbSession,
    paging: Paging,
    search: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
    low_stock: bool = False,
    expiring_within_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
    include_inactive: bool = False,
) -> dict:
    return pharmacy_service.list_medicines(
        db,
        search=search,
        category=category,
        low_stock=low_stock,
        expiring_within_days=expiring_within_days,
        include_inactive=include_inactive,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/medicines/alerts", response_model=MedicineAlerts)
def medicine_alerts(
    _: PharmacyUser, db: DbSession, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> dict:
    return pharmacy_service.alerts(db, days)


@router.get("/medicines/usage", response_model=StockUsage)
def stock_usage(
    _: PharmacyUser, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30
) -> dict:
    return pharmacy_service.stock_usage(db, days)


@router.get("/medicines/categories", response_model=list[str])
def medicine_categories(_: MedicineReader, db: DbSession) -> list[str]:
    return pharmacy_service.list_categories(db)


@router.post("/medicines", response_model=MedicineOut, status_code=status.HTTP_201_CREATED)
def create_medicine(body: MedicineCreate, user: PharmacyUser, db: DbSession) -> object:
    return pharmacy_service.create_medicine(db, body, user)


@router.get("/medicines/{medicine_id}", response_model=MedicineOut)
def get_medicine(medicine_id: int, _: MedicineReader, db: DbSession) -> object:
    return get_or_404(db, Medicine, medicine_id, "Medicine")


@router.patch("/medicines/{medicine_id}", response_model=MedicineOut)
def update_medicine(
    medicine_id: int, body: MedicineUpdate, _: PharmacyUser, db: DbSession
) -> object:
    medicine = get_or_404(db, Medicine, medicine_id, "Medicine")
    return pharmacy_service.update_medicine(db, medicine, body)


@router.delete("/medicines/{medicine_id}", response_model=MedicineOut)
def deactivate_medicine(medicine_id: int, _: PharmacyUser, db: DbSession) -> object:
    medicine = get_or_404(db, Medicine, medicine_id, "Medicine")
    return pharmacy_service.deactivate_medicine(db, medicine)


@router.post("/medicines/{medicine_id}/stock", response_model=MedicineOut)
def adjust_stock(
    medicine_id: int, body: StockAdjustment, user: PharmacyUser, db: DbSession
) -> object:
    return pharmacy_service.adjust_stock(db, medicine_id, body, user)


@router.get("/medicines/{medicine_id}/movements", response_model=Page[StockMovementOut])
def stock_movements(medicine_id: int, _: PharmacyUser, db: DbSession, paging: Paging) -> dict:
    return pharmacy_service.list_movements(db, medicine_id, paging.page, paging.page_size)


# ---------------- Prescriptions ----------------
def _get_visible_prescription(db, prescription_id: int, user: User) -> Prescription:
    prescription = get_or_404(db, Prescription, prescription_id, "Prescription")
    if user.role == Role.DOCTOR and prescription.doctor_id != user.doctor_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Prescription {prescription_id} not found")
    return prescription


@router.get("/prescriptions", response_model=Page[PrescriptionOut])
def list_prescriptions(
    user: PrescriptionReader,
    db: DbSession,
    paging: Paging,
    status: PrescriptionStatus | None = None,
    patient_id: int | None = None,
    doctor_id: int | None = None,
) -> dict:
    return pharmacy_service.list_prescriptions(
        db,
        status=status,
        patient_id=patient_id,
        doctor_id=scoped_doctor_id(user, doctor_id),
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def create_prescription(body: PrescriptionCreate, user: PrescriberUser, db: DbSession) -> object:
    return pharmacy_service.create_prescription(db, body, user)


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionOut)
def get_prescription(prescription_id: int, user: PrescriptionReader, db: DbSession) -> object:
    return _get_visible_prescription(db, prescription_id, user)


@router.post("/prescriptions/{prescription_id}/dispense", response_model=PrescriptionOut)
def dispense_prescription(prescription_id: int, user: PharmacyUser, db: DbSession) -> object:
    return pharmacy_service.dispense_prescription(db, prescription_id, user)


@router.post("/prescriptions/{prescription_id}/cancel", response_model=PrescriptionOut)
def cancel_prescription(prescription_id: int, user: PrescriberUser, db: DbSession) -> object:
    _get_visible_prescription(db, prescription_id, user)
    return pharmacy_service.cancel_prescription(db, prescription_id)
