from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import ClinicalDeskUser, DbSession, FrontDeskUser, Paging, StaffUser
from app.models import Patient
from app.models.enums import BloodGroup, Gender, Role
from app.schemas.appointment import AppointmentOut
from app.schemas.common import Page
from app.schemas.history import PatientHistory
from app.schemas.patient import PatientCreate, PatientOut, PatientUpdate
from app.services import patient_service
from app.services.common import get_or_404

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=Page[PatientOut])
def list_patients(
    _: StaffUser,
    db: DbSession,
    paging: Paging,
    search: Annotated[str | None, Query(max_length=100)] = None,
    gender: Gender | None = None,
    blood_group: BloodGroup | None = None,
) -> dict:
    return patient_service.list_patients(
        db,
        search=search,
        gender=gender,
        blood_group=blood_group,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientCreate, _: FrontDeskUser, db: DbSession) -> object:
    return patient_service.create_patient(db, body)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, _: StaffUser, db: DbSession) -> object:
    return get_or_404(db, Patient, patient_id, "Patient")


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, body: PatientUpdate, _: FrontDeskUser, db: DbSession) -> object:
    patient = get_or_404(db, Patient, patient_id, "Patient")
    return patient_service.update_patient(db, patient, body)


@router.get("/{patient_id}/history", response_model=PatientHistory)
def patient_history(patient_id: int, user: ClinicalDeskUser, db: DbSession) -> PatientHistory:
    """Full timeline. Receptionists get a redacted view without clinical details."""
    patient = get_or_404(db, Patient, patient_id, "Patient")
    history = PatientHistory.model_validate(
        patient_service.patient_history(db, patient), from_attributes=True
    )
    if user.role == Role.RECEPTIONIST:
        history.appointments = [
            AppointmentOut.model_validate(a.model_dump() | {"diagnosis": None, "notes": None})
            for a in history.appointments
        ]
        history.prescriptions = []
        history.clinical_details_redacted = True
    return history
