from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Numeric, Sequence, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import InvoiceItemType, InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.patient import Patient

invoice_number_seq = Sequence("invoice_number_seq", metadata=Base.metadata)


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount >= 0", name="discount_non_negative"),
        CheckConstraint("tax >= 0", name="tax_non_negative"),
        CheckConstraint("total >= 0", name="total_non_negative"),
    )
    __mapper_args__ = {"eager_defaults": True}  # fetch invoice_number via RETURNING

    invoice_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        server_default=text(
            "'INV-' || to_char(now(), 'YYYY') || '-' "
            "|| lpad(nextval('invoice_number_seq')::text, 6, '0')"
        ),
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    admission_id: Mapped[int | None] = mapped_column(
        ForeignKey("admissions.id", ondelete="SET NULL"), index=True
    )
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    due_date: Mapped[date | None]
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0")
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[InvoiceStatus] = mapped_column(
        str_enum(InvoiceStatus, "invoice_status", 20),
        default=InvoiceStatus.UNPAID,
        server_default=InvoiceStatus.UNPAID.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    patient: Mapped[Patient] = relationship(lazy="joined", innerjoin=True)
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InvoiceItem.id",
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", lazy="selectin", order_by="Payment.paid_at"
    )

    @property
    def patient_name(self) -> str:
        return self.patient.full_name

    @property
    def patient_code(self) -> str:
        return self.patient.patient_code

    @property
    def amount_paid(self) -> Decimal:
        return sum(
            (p.amount for p in self.payments if p.status == PaymentStatus.SUCCESS), Decimal("0")
        )

    @property
    def balance_due(self) -> Decimal:
        if self.status == InvoiceStatus.CANCELLED:
            return Decimal("0")
        return max(self.total - self.amount_paid, Decimal("0"))


class InvoiceItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price >= 0", name="price_non_negative"),
    )

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[InvoiceItemType] = mapped_column(
        str_enum(InvoiceItemType, "invoice_item_type", 15)
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), Computed("quantity * unit_price", persisted=True)
    )
    # Traceability to the billed source (prevents double billing in the service layer).
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), index=True
    )
    prescription_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescription_items.id", ondelete="SET NULL"), index=True
    )
    admission_id: Mapped[int | None] = mapped_column(
        ForeignKey("admissions.id", ondelete="SET NULL"), index=True
    )

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class Payment(IdMixin, TimestampMixin, Base):
    """Simulated payment record - no real payment gateway is ever contacted."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="positive_amount"),)

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    method: Mapped[PaymentMethod] = mapped_column(str_enum(PaymentMethod, "payment_method", 20))
    status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus, "payment_status", 15))
    transaction_ref: Mapped[str] = mapped_column(String(40), unique=True)
    paid_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    invoice: Mapped[Invoice] = relationship(back_populates="payments")

    @property
    def invoice_number(self) -> str:
        return self.invoice.invoice_number

    @property
    def patient_name(self) -> str:
        return self.invoice.patient.full_name
