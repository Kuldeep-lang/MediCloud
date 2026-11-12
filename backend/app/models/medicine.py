from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutils import local_today
from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin, str_enum
from app.models.enums import StockReason


class Medicine(IdMixin, TimestampMixin, Base):
    __tablename__ = "medicines"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
        CheckConstraint("reorder_level >= 0", name="reorder_non_negative"),
        Index(
            "ix_medicines_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    generic_name: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(60), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    dosage_form: Mapped[str | None] = mapped_column(String(30))
    strength: Mapped[str | None] = mapped_column(String(30))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(default=0, server_default="0")
    reorder_level: Mapped[int] = mapped_column(default=10, server_default="10")
    batch_number: Mapped[str | None] = mapped_column(String(40))
    expiry_date: Mapped[date] = mapped_column(index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    @property
    def is_low_stock(self) -> bool:
        return self.stock_quantity <= self.reorder_level

    @property
    def days_to_expiry(self) -> int:
        return (self.expiry_date - local_today()).days

    @property
    def is_expired(self) -> bool:
        return self.days_to_expiry < 0


class StockMovement(IdMixin, CreatedAtMixin, Base):
    """Append-only stock ledger: every change to stock_quantity is recorded here."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change_quantity <> 0", name="non_zero_change"),
        CheckConstraint("balance_after >= 0", name="balance_non_negative"),
        Index("ix_stock_movements_medicine_created", "medicine_id", "created_at"),
    )

    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"))
    change_quantity: Mapped[int]
    balance_after: Mapped[int]
    reason: Mapped[StockReason] = mapped_column(str_enum(StockReason, "stock_reason", 15))
    reference: Mapped[str | None] = mapped_column(String(60))
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    medicine: Mapped[Medicine] = relationship(lazy="joined", innerjoin=True)

    @property
    def medicine_name(self) -> str:
        return self.medicine.name
