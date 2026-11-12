from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.doctor import Doctor
from app.models.enums import PrescriptionStatus
from app.models.medicine import Medicine
from app.models.patient import Patient


class Prescription(IdMixin, TimestampMixin, Base):
    __tablename__ = "prescriptions"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), index=True
    )
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[PrescriptionStatus] = mapped_column(
        str_enum(PrescriptionStatus, "prescription_status", 15),
        default=PrescriptionStatus.PENDING,
        server_default=PrescriptionStatus.PENDING.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    dispensed_at: Mapped[datetime | None]
    dispensed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    patient: Mapped[Patient] = relationship(lazy="joined", innerjoin=True)
    doctor: Mapped[Doctor] = relationship(lazy="joined", innerjoin=True)
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PrescriptionItem.id",
    )

    @property
    def patient_name(self) -> str:
        return self.patient.full_name

    @property
    def patient_code(self) -> str:
        return self.patient.patient_code

    @property
    def doctor_name(self) -> str:
        return self.doctor.full_name


class PrescriptionItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "prescription_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="positive_duration"),
        UniqueConstraint("prescription_id", "medicine_id"),
    )

    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"))
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicines.id", ondelete="RESTRICT"), index=True
    )
    dosage: Mapped[str] = mapped_column(String(60))
    frequency: Mapped[str] = mapped_column(String(60))
    duration_days: Mapped[int | None] = mapped_column(SmallInteger)
    quantity: Mapped[int]
    instructions: Mapped[str | None] = mapped_column(String(255))

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    medicine: Mapped[Medicine] = relationship(lazy="joined", innerjoin=True)

    @property
    def medicine_name(self) -> str:
        return self.medicine.name

    @property
    def unit_price(self):
        return self.medicine.unit_price
