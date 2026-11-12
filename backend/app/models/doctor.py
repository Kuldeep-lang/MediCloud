from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.department import Department

if TYPE_CHECKING:
    from app.models.user import User


class Doctor(IdMixin, TimestampMixin, Base):
    __tablename__ = "doctors"
    __table_args__ = (
        CheckConstraint("consultation_fee >= 0", name="fee_non_negative"),
        CheckConstraint("years_experience >= 0", name="experience_non_negative"),
        Index("ix_doctors_name", "last_name", "first_name"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    specialization: Mapped[str] = mapped_column(String(100), index=True)
    license_number: Mapped[str] = mapped_column(String(40), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str] = mapped_column(String(20))
    consultation_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    years_experience: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    department: Mapped[Department] = relationship(lazy="joined", innerjoin=True)
    user: Mapped["User | None"] = relationship(back_populates="doctor")
    schedules: Mapped[list["DoctorSchedule"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        order_by="(DoctorSchedule.day_of_week, DoctorSchedule.start_time)",
    )

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"

    @property
    def department_name(self) -> str:
        return self.department.name


class DoctorSchedule(IdMixin, TimestampMixin, Base):
    """Weekly availability block. day_of_week: 0 = Monday ... 6 = Sunday."""

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="valid_day"),
        CheckConstraint("end_time > start_time", name="end_after_start"),
        CheckConstraint("slot_minutes > 0", name="positive_slot"),
        UniqueConstraint("doctor_id", "day_of_week", "start_time"),
    )

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time]
    end_time: Mapped[time]
    slot_minutes: Mapped[int] = mapped_column(SmallInteger, default=15, server_default="15")

    doctor: Mapped[Doctor] = relationship(back_populates="schedules")
