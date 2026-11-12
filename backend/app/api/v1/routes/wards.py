"""Wards, beds and admissions (bed allocation / discharge)."""

from fastapi import APIRouter, status

from app.core.deps import AdminUser, ClinicalDeskUser, DbSession, FrontDeskUser, Paging
from app.models import Admission, Ward
from app.models.enums import AdmissionStatus, BedStatus
from app.schemas.common import Page
from app.schemas.ward import (
    AdmissionCreate,
    AdmissionOut,
    BedCreate,
    BedOut,
    BedUpdate,
    DischargeRequest,
    OccupancySummary,
    WardCreate,
    WardOut,
    WardUpdate,
)
from app.services import ward_service
from app.services.common import get_or_404

router = APIRouter(tags=["wards & beds"])


# ---------------- Wards ----------------
@router.get("/wards", response_model=list[WardOut])
def list_wards(_: ClinicalDeskUser, db: DbSession) -> list:
    return ward_service.list_wards(db)


@router.post("/wards", response_model=WardOut, status_code=status.HTTP_201_CREATED)
def create_ward(body: WardCreate, _: AdminUser, db: DbSession) -> dict:
    return ward_service.create_ward(db, body)


@router.patch("/wards/{ward_id}", response_model=WardOut)
def update_ward(ward_id: int, body: WardUpdate, _: AdminUser, db: DbSession) -> dict:
    ward = get_or_404(db, Ward, ward_id, "Ward")
    return ward_service.update_ward(db, ward, body)


# ---------------- Beds ----------------
@router.get("/beds/occupancy", response_model=OccupancySummary)
def bed_occupancy(_: ClinicalDeskUser, db: DbSession) -> dict:
    return ward_service.occupancy_summary(db)


@router.get("/beds", response_model=list[BedOut])
def list_beds(
    _: ClinicalDeskUser,
    db: DbSession,
    ward_id: int | None = None,
    status: BedStatus | None = None,
) -> list:
    return ward_service.list_beds(db, ward_id=ward_id, status=status)


@router.post("/beds", response_model=BedOut, status_code=status.HTTP_201_CREATED)
def create_bed(body: BedCreate, _: AdminUser, db: DbSession) -> dict:
    return ward_service.create_bed(db, body)


@router.patch("/beds/{bed_id}", response_model=BedOut)
def update_bed(bed_id: int, body: BedUpdate, _: AdminUser, db: DbSession) -> dict:
    return ward_service.set_bed_status(db, bed_id, body.status)


# ---------------- Admissions ----------------
@router.get("/admissions", response_model=Page[AdmissionOut])
def list_admissions(
    _: ClinicalDeskUser,
    db: DbSession,
    paging: Paging,
    status: AdmissionStatus | None = None,
    patient_id: int | None = None,
) -> dict:
    return ward_service.list_admissions(
        db, status=status, patient_id=patient_id, page=paging.page, page_size=paging.page_size
    )


@router.post("/admissions", response_model=AdmissionOut, status_code=status.HTTP_201_CREATED)
def admit_patient(body: AdmissionCreate, user: FrontDeskUser, db: DbSession) -> object:
    return ward_service.admit_patient(db, body, user)


@router.get("/admissions/{admission_id}", response_model=AdmissionOut)
def get_admission(admission_id: int, _: ClinicalDeskUser, db: DbSession) -> object:
    return get_or_404(db, Admission, admission_id, "Admission")


@router.post("/admissions/{admission_id}/discharge", response_model=AdmissionOut)
def discharge_patient(
    admission_id: int, body: DischargeRequest, _: ClinicalDeskUser, db: DbSession
) -> object:
    admission = get_or_404(db, Admission, admission_id, "Admission")
    return ward_service.discharge_patient(db, admission, body.discharge_summary)
