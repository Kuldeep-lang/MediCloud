from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.enums import AppointmentStatus
from app.schemas.common import LocalDateTime, LongText, ORMModel, ShortText

Duration = Annotated[int, Field(ge=5, le=240)]


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    scheduled_at: LocalDateTime
    duration_minutes: Duration = 15
    reason: ShortText | None = None


class AppointmentUpdate(BaseModel):
    """Reschedule and/or reassign. Only allowed while scheduled or confirmed."""

    doctor_id: int | None = None
    scheduled_at: LocalDateTime | None = None
    duration_minutes: Duration | None = None
    reason: ShortText | None = None


class AppointmentCancel(BaseModel):
    reason: ShortText | None = None


class AppointmentStatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "no_show"]
    diagnosis: LongText | None = None
    notes: LongText | None = None


class AppointmentOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    department_name: str
    scheduled_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    reason: str | None
    diagnosis: str | None
    notes: str | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
