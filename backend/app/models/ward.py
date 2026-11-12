from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import BedStatus, WardType


class Ward(IdMixin, TimestampMixin, Base):
    __tablename__ = "wards"
    __table_args__ = (CheckConstraint("daily_rate >= 0", name="rate_non_negative"),)

    name: Mapped[str] = mapped_column(String(60), unique=True)
    ward_type: Mapped[WardType] = mapped_column(str_enum(WardType, "ward_type", 15))
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    beds: Mapped[list["Bed"]] = relationship(back_populates="ward", order_by="Bed.bed_number")


class Bed(IdMixin, TimestampMixin, Base):
    __tablename__ = "beds"
    __table_args__ = (
        UniqueConstraint("ward_id", "bed_number"),
        Index("ix_beds_ward_status", "ward_id", "status"),
    )

    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id", ondelete="RESTRICT"))
    bed_number: Mapped[str] = mapped_column(String(10))
    status: Mapped[BedStatus] = mapped_column(
        str_enum(BedStatus, "bed_status", 15),
        default=BedStatus.AVAILABLE,
        server_default=BedStatus.AVAILABLE.value,
        index=True,
    )

    ward: Mapped[Ward] = relationship(back_populates="beds", lazy="joined", innerjoin=True)
