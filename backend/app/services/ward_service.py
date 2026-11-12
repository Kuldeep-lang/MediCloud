from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.timeutils import now_utc
from app.models import Admission, Bed, Doctor, Patient, User, Ward
from app.models.enums import AdmissionStatus, BedStatus
from app.schemas.ward import AdmissionCreate, BedCreate, WardCreate, WardUpdate
from app.services.common import get_or_404, paginate


# ---------------- Wards ----------------
def _bed_counts(db: Session) -> dict[int, dict[str, int]]:
    rows = db.execute(
        select(Bed.ward_id, Bed.status, func.count()).group_by(Bed.ward_id, Bed.status)
    ).all()
    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ward_id, status, count in rows:
        counts[ward_id][status.value] = count
    return counts


def _ward_dict(ward: Ward, counts: dict[str, int]) -> dict:
    available = counts.get("available", 0)
    occupied = counts.get("occupied", 0)
    maintenance = counts.get("maintenance", 0)
    return {
        "id": ward.id,
        "name": ward.name,
        "ward_type": ward.ward_type,
        "floor": ward.floor,
        "daily_rate": ward.daily_rate,
        "total_beds": available + occupied + maintenance,
        "available_beds": available,
        "occupied_beds": occupied,
        "maintenance_beds": maintenance,
    }


def list_wards(db: Session) -> list[dict]:
    counts = _bed_counts(db)
    wards = db.scalars(select(Ward).order_by(Ward.name)).all()
    return [_ward_dict(w, counts.get(w.id, {})) for w in wards]


def create_ward(db: Session, data: WardCreate) -> dict:
    if db.scalar(select(Ward.id).where(Ward.name == data.name)):
        raise ConflictError("A ward with this name already exists")
    ward = Ward(**data.model_dump())
    db.add(ward)
    db.commit()
    return _ward_dict(ward, {})


def update_ward(db: Session, ward: Ward, data: WardUpdate) -> dict:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes and db.scalar(
        select(Ward.id).where(Ward.name == changes["name"], Ward.id != ward.id)
    ):
        raise ConflictError("A ward with this name already exists")
    for key, value in changes.items():
        setattr(ward, key, value)
    db.commit()
    return _ward_dict(ward, _bed_counts(db).get(ward.id, {}))


def occupancy_summary(db: Session) -> dict:
    wards = list_wards(db)
    by_type: dict[str, dict[str, float]] = defaultdict(
        lambda: {"total": 0, "available": 0, "occupied": 0, "maintenance": 0}
    )
    overall = {"total": 0, "available": 0, "occupied": 0, "maintenance": 0}
    for w in wards:
        bucket = by_type[w["ward_type"].value]
        for key, field in (
            ("total", "total_beds"),
            ("available", "available_beds"),
            ("occupied", "occupied_beds"),
            ("maintenance", "maintenance_beds"),
        ):
            bucket[key] += w[field]
            overall[key] += w[field]

    def with_rate(b: dict) -> dict:
        rate = round(b["occupied"] / b["total"] * 100, 1) if b["total"] else 0.0
        return {**b, "occupancy_rate": rate}

    return {
        "overall": with_rate(overall),
        "by_ward_type": {k: with_rate(v) for k, v in by_type.items()},
        "wards": wards,
    }


# ---------------- Beds ----------------
def _bed_dict(bed: Bed, admission: Admission | None) -> dict:
    return {
        "id": bed.id,
        "ward_id": bed.ward_id,
        "ward_name": bed.ward.name,
        "ward_type": bed.ward.ward_type,
        "bed_number": bed.bed_number,
        "status": bed.status,
        "current_admission_id": admission.id if admission else None,
        "current_patient_name": admission.patient.full_name if admission else None,
        "current_patient_code": admission.patient.patient_code if admission else None,
        "admitted_at": admission.admitted_at if admission else None,
    }


def list_beds(db: Session, *, ward_id: int | None, status: BedStatus | None) -> list[dict]:
    stmt = select(Bed).order_by(Bed.ward_id, Bed.bed_number)
    if ward_id:
        stmt = stmt.where(Bed.ward_id == ward_id)
    if status:
        stmt = stmt.where(Bed.status == status)
    beds = db.scalars(stmt).all()
    active = {
        a.bed_id: a
        for a in db.scalars(
            select(Admission).where(
                Admission.status == AdmissionStatus.ADMITTED,
                Admission.bed_id.in_([b.id for b in beds]),
            )
        )
    }
    return [_bed_dict(b, active.get(b.id)) for b in beds]


def create_bed(db: Session, data: BedCreate) -> dict:
    get_or_404(db, Ward, data.ward_id, "Ward")
    exists = db.scalar(
        select(Bed.id).where(Bed.ward_id == data.ward_id, Bed.bed_number == data.bed_number)
    )
    if exists:
        raise ConflictError("This bed number already exists in the ward")
    bed = Bed(ward_id=data.ward_id, bed_number=data.bed_number)
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return _bed_dict(bed, None)


def _lock_bed(db: Session, bed_id: int) -> Bed:
    bed = db.scalar(
        select(Bed)
        .where(Bed.id == bed_id)
        .with_for_update(of=Bed)
        .execution_options(populate_existing=True)
    )
    if bed is None:
        raise NotFoundError(f"Bed {bed_id} not found")
    return bed


def set_bed_status(db: Session, bed_id: int, status: str) -> dict:
    bed = _lock_bed(db, bed_id)
    if bed.status == BedStatus.OCCUPIED:
        raise BusinessRuleError("An occupied bed cannot be changed - discharge the patient first")
    bed.status = BedStatus(status)
    db.commit()
    return _bed_dict(bed, None)


# ---------------- Admissions ----------------
def list_admissions(
    db: Session,
    *,
    status: AdmissionStatus | None,
    patient_id: int | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Admission).order_by(Admission.admitted_at.desc())
    if status:
        stmt = stmt.where(Admission.status == status)
    if patient_id:
        stmt = stmt.where(Admission.patient_id == patient_id)
    return paginate(db, stmt, page, page_size)


def admit_patient(db: Session, data: AdmissionCreate, user: User) -> Admission:
    get_or_404(db, Patient, data.patient_id, "Patient")
    if data.admitting_doctor_id:
        doctor = db.get(Doctor, data.admitting_doctor_id)
        if doctor is None or not doctor.is_active:
            raise BusinessRuleError("Admitting doctor does not exist or is inactive")
    bed = _lock_bed(db, data.bed_id)  # serialises concurrent allocations of this bed
    if bed.status != BedStatus.AVAILABLE:
        raise ConflictError(f"Bed {bed.bed_number} is not available ({bed.status.value})")
    already = db.scalar(
        select(Admission.id).where(
            Admission.patient_id == data.patient_id, Admission.status == AdmissionStatus.ADMITTED
        )
    )
    if already:
        raise ConflictError("This patient is already admitted")
    admission = Admission(
        patient_id=data.patient_id,
        bed_id=bed.id,
        admitting_doctor_id=data.admitting_doctor_id,
        reason=data.reason,
        admitted_at=now_utc(),
    )
    bed.status = BedStatus.OCCUPIED
    db.add(admission)
    db.commit()
    db.refresh(admission)
    return admission


def discharge_patient(db: Session, admission: Admission, summary: str | None) -> Admission:
    if admission.status != AdmissionStatus.ADMITTED:
        raise BusinessRuleError("This admission has already been discharged")
    bed = _lock_bed(db, admission.bed_id)
    admission.status = AdmissionStatus.DISCHARGED
    admission.discharged_at = now_utc()
    admission.discharge_summary = summary
    bed.status = BedStatus.AVAILABLE
    db.commit()
    db.refresh(admission)
    return admission
