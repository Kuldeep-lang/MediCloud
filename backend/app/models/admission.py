from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.doctor import Doctor
from app.models.enums import AdmissionStatus
from app.models.patient import Patient
from app.models.ward import Bed


class Admission(IdMixin, TimestampMixin, Base):
    __tablename__ = "admissions"
    __table_args__ = (
        CheckConstraint(
            "discharged_at IS NULL OR discharged_at >= admitted_at", name="discharge_after_admit"
        ),
        CheckConstraint(
            "(status = 'discharged') = (discharged_at IS NOT NULL)", name="status_matches_discharge"
        ),
        # One patient per bed, and one active admission per patient - enforced by the DB.
        Index(
            "uq_admissions_active_bed",
            "bed_id",
            unique=True,
            postgresql_where=text("status = 'admitted'"),
        ),
        Index(
            "uq_admissions_active_patient",
            "patient_id",
            unique=True,
            postgresql_where=text("status = 'admitted'"),
        ),
        Index("ix_admissions_patient_id", "patient_id"),
        Index("ix_admissions_bed_id", "bed_id"),
    )

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id", ondelete="RESTRICT"))
    admitting_doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id", ondelete="SET NULL"), index=True
    )
    admitted_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    discharged_at: Mapped[datetime | None]
    status: Mapped[AdmissionStatus] = mapped_column(
        str_enum(AdmissionStatus, "admission_status", 15),
        default=AdmissionStatus.ADMITTED,
        server_default=AdmissionStatus.ADMITTED.value,
    )
    reason: Mapped[str] = mapped_column(Text)
    discharge_summary: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(lazy="joined", innerjoin=True)
    bed: Mapped[Bed] = relationship(lazy="joined", innerjoin=True)
    admitting_doctor: Mapped[Doctor | None] = relationship(lazy="joined")

    @property
    def patient_name(self) -> str:
        return self.patient.full_name

    @property
    def patient_code(self) -> str:
        return self.patient.patient_code

    @property
    def bed_number(self) -> str:
        return self.bed.bed_number

    @property
    def ward_name(self) -> str:
        return self.bed.ward.name

    @property
    def ward_type(self) -> str:
        return self.bed.ward.ward_type

    @property
    def doctor_name(self) -> str | None:
        return self.admitting_doctor.full_name if self.admitting_doctor else None
