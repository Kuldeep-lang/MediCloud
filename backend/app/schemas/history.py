from pydantic import BaseModel

from app.schemas.appointment import AppointmentOut
from app.schemas.patient import PatientOut
from app.schemas.pharmacy import PrescriptionOut
from app.schemas.ward import AdmissionOut


class PatientHistory(BaseModel):
    patient: PatientOut
    appointments: list[AppointmentOut]
    prescriptions: list[PrescriptionOut]
    admissions: list[AdmissionOut]
    clinical_details_redacted: bool = False
