from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient


class Appointment(IdMixin, TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="positive_duration"),
        Index("ix_appointments_doctor_time", "doctor_id", "scheduled_at"),
        Index("ix_appointments_patient_time", "patient_id", "scheduled_at"),
        # The database itself prevents double-booking the same doctor slot.
        Index(
            "uq_appointments_doctor_active_slot",
            "doctor_id",
            "scheduled_at",
            unique=True,
            postgresql_where=text("status IN ('scheduled', 'confirmed')"),
        ),
    )

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"))
    scheduled_at: Mapped[datetime] = mapped_column(index=True)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, default=15, server_default="15")
    status: Mapped[AppointmentStatus] = mapped_column(
        str_enum(AppointmentStatus, "appointment_status", 15),
        default=AppointmentStatus.SCHEDULED,
        server_default=AppointmentStatus.SCHEDULED.value,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    patient: Mapped[Patient] = relationship(lazy="joined", innerjoin=True)
    doctor: Mapped[Doctor] = relationship(lazy="joined", innerjoin=True)

    @property
    def patient_name(self) -> str:
        return self.patient.full_name

    @property
    def patient_code(self) -> str:
        return self.patient.patient_code

    @property
    def doctor_name(self) -> str:
        return self.doctor.full_name

    @property
    def department_name(self) -> str:
        return self.doctor.department.name
