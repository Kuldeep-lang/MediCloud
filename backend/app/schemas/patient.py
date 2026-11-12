from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr

from app.core.timeutils import local_today
from app.models.enums import BloodGroup, Gender
from app.schemas.common import LongText, Name, ORMModel, Phone, ShortText


def _validate_dob(value: date) -> date:
    today = local_today()
    if value > today:
        raise ValueError("date_of_birth cannot be in the future")
    if value.year < today.year - 130:
        raise ValueError("date_of_birth is not plausible")
    return value


DateOfBirth = Annotated[date, AfterValidator(_validate_dob)]


class PatientBase(BaseModel):
    first_name: Name
    last_name: Name
    date_of_birth: DateOfBirth
    gender: Gender
    phone: Phone
    email: EmailStr | None = None
    address: LongText | None = None
    blood_group: BloodGroup | None = None
    emergency_contact_name: ShortText | None = None
    emergency_contact_phone: Phone | None = None
    allergies: LongText | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    date_of_birth: DateOfBirth | None = None
    gender: Gender | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    address: LongText | None = None
    blood_group: BloodGroup | None = None
    emergency_contact_name: ShortText | None = None
    emergency_contact_phone: Phone | None = None
    allergies: LongText | None = None


class PatientOut(ORMModel):
    id: int
    patient_code: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date
    age: int
    gender: Gender
    phone: str
    email: str | None
    address: str | None
    blood_group: BloodGroup | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    allergies: str | None
    created_at: datetime
    updated_at: datetime


class PatientSummary(ORMModel):
    id: int
    patient_code: str
    full_name: str
    age: int
    gender: Gender
    phone: str
