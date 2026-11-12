from datetime import datetime, time
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from app.schemas.common import Money, MoneyIn, Name, ORMModel, Phone

Specialization = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
]
License = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9\-/]{4,40}$")
]


class ScheduleBlock(BaseModel):
    day_of_week: Annotated[int, Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")]
    start_time: time
    end_time: time
    slot_minutes: Annotated[int, Field(ge=5, le=120)] = 15

    @model_validator(mode="after")
    def _check_times(self) -> "ScheduleBlock":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleOut(ScheduleBlock, ORMModel):
    id: int


class DoctorOut(ORMModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    specialization: str
    department_id: int
    department_name: str
    license_number: str
    email: str
    phone: str
    consultation_fee: Money
    years_experience: int
    is_active: bool
    user_id: int | None
    created_at: datetime


class DoctorDetail(DoctorOut):
    schedules: list[ScheduleOut]


class DoctorCreate(BaseModel):
    first_name: Name
    last_name: Name
    specialization: Specialization
    department_id: int
    license_number: License
    email: EmailStr
    phone: Phone
    consultation_fee: MoneyIn
    years_experience: Annotated[int, Field(ge=0, le=70)] = 0
    user_id: int | None = None
    schedules: list[ScheduleBlock] = []


class DoctorUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    specialization: Specialization | None = None
    department_id: int | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    consultation_fee: MoneyIn | None = None
    years_experience: Annotated[int, Field(ge=0, le=70)] | None = None
    is_active: bool | None = None
    user_id: int | None = None


class AvailabilitySlot(BaseModel):
    start: datetime
    end: datetime
    available: bool
