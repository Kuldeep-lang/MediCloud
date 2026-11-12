from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import AdmissionStatus, BedStatus, WardType
from app.schemas.common import LongText, Money, MoneyIn, ORMModel

WardName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
BedNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9\-]{1,10}$")
]


class WardCreate(BaseModel):
    name: WardName
    ward_type: WardType
    floor: Annotated[int, Field(ge=-5, le=200)] | None = None
    daily_rate: MoneyIn


class WardUpdate(BaseModel):
    name: WardName | None = None
    floor: Annotated[int, Field(ge=-5, le=200)] | None = None
    daily_rate: MoneyIn | None = None


class WardOut(ORMModel):
    id: int
    name: str
    ward_type: WardType
    floor: int | None
    daily_rate: Money
    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    maintenance_beds: int = 0


class BedCreate(BaseModel):
    ward_id: int
    bed_number: BedNumber


class BedUpdate(BaseModel):
    status: Literal["available", "maintenance"]


class BedOut(ORMModel):
    id: int
    ward_id: int
    ward_name: str
    ward_type: WardType
    bed_number: str
    status: BedStatus
    current_admission_id: int | None = None
    current_patient_name: str | None = None
    current_patient_code: str | None = None
    admitted_at: datetime | None = None


class OccupancyBucket(BaseModel):
    total: int = 0
    available: int = 0
    occupied: int = 0
    maintenance: int = 0
    occupancy_rate: float = 0.0


class OccupancySummary(BaseModel):
    overall: OccupancyBucket
    by_ward_type: dict[str, OccupancyBucket]
    wards: list[WardOut]


class AdmissionCreate(BaseModel):
    patient_id: int
    bed_id: int
    admitting_doctor_id: int | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class DischargeRequest(BaseModel):
    discharge_summary: LongText | None = None


class AdmissionOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    bed_id: int
    bed_number: str
    ward_name: str
    ward_type: WardType
    admitting_doctor_id: int | None
    doctor_name: str | None
    admitted_at: datetime
    discharged_at: datetime | None
    status: AdmissionStatus
    reason: str
    discharge_summary: str | None
