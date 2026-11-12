from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Admission, Appointment, Patient, Prescription
from app.models.enums import BloodGroup, Gender
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.common import like_term, paginate


def list_patients(
    db: Session,
    *,
    search: str | None,
    gender: Gender | None,
    blood_group: BloodGroup | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Patient).order_by(Patient.created_at.desc(), Patient.id.desc())
    if search:
        term = like_term(search)
        full_name = Patient.first_name + " " + Patient.last_name
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(term, escape="\\"),
                Patient.last_name.ilike(term, escape="\\"),
                full_name.ilike(term, escape="\\"),
                Patient.patient_code.ilike(term, escape="\\"),
                Patient.phone.ilike(term, escape="\\"),
                Patient.email.ilike(term, escape="\\"),
            )
        )
    if gender:
        stmt = stmt.where(Patient.gender == gender)
    if blood_group:
        stmt = stmt.where(Patient.blood_group == blood_group)
    return paginate(db, stmt, page, page_size)


def create_patient(db: Session, data: PatientCreate) -> Patient:
    fields = data.model_dump()
    if fields.get("email"):
        fields["email"] = fields["email"].lower()
    patient = Patient(**fields)
    db.add(patient)
    db.commit()
    return patient


def update_patient(db: Session, patient: Patient, data: PatientUpdate) -> Patient:
    changes = data.model_dump(exclude_unset=True)
    required = {"first_name", "last_name", "date_of_birth", "gender", "phone"}
    for key, value in changes.items():
        if value is None and key in required:
            continue  # required columns cannot be cleared
        if key == "email" and value:
            value = value.lower()
        setattr(patient, key, value)
    db.commit()
    return patient


def patient_history(db: Session, patient: Patient) -> dict:
    appointments = db.scalars(
        select(Appointment)
        .where(Appointment.patient_id == patient.id)
        .order_by(Appointment.scheduled_at.desc())
    ).all()
    prescriptions = db.scalars(
        select(Prescription)
        .where(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc())
    ).all()
    admissions = db.scalars(
        select(Admission)
        .where(Admission.patient_id == patient.id)
        .order_by(Admission.admitted_at.desc())
    ).all()
    return {
        "patient": patient,
        "appointments": list(appointments),
        "prescriptions": list(prescriptions),
        "admissions": list(admissions),
    }
