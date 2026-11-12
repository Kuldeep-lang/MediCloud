"""Invoices and SIMULATED payments (no real payment gateway)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, FrontDeskUser, Paging
from app.models import Invoice
from app.models.enums import InvoiceStatus
from app.schemas.billing import (
    BillableSummary,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceGenerate,
    InvoiceOut,
    PaymentCreate,
    PaymentListItem,
    PaymentOut,
)
from app.schemas.common import Page
from app.services import billing_service
from app.services.common import get_or_404

router = APIRouter(tags=["billing"])


@router.get("/invoices", response_model=Page[InvoiceOut])
def list_invoices(
    _: FrontDeskUser,
    db: DbSession,
    paging: Paging,
    patient_id: int | None = None,
    status: InvoiceStatus | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    return billing_service.list_invoices(
        db,
        patient_id=patient_id,
        status=status,
        search=search,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/invoices/billable", response_model=BillableSummary)
def billable(patient_id: int, _: FrontDeskUser, db: DbSession) -> dict:
    """Preview everything not yet billed for a patient (consultations, medicines, room)."""
    items = billing_service.billable_items(db, patient_id)
    subtotal = sum((Decimal(i["line_total"]) for i in items), Decimal("0"))
    return {"patient_id": patient_id, "items": items, "subtotal": subtotal}


@router.post("/invoices", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED)
def create_invoice(body: InvoiceCreate, user: FrontDeskUser, db: DbSession) -> object:
    return billing_service.create_invoice(db, body, user)


@router.post(
    "/invoices/generate", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED
)
def generate_invoice(body: InvoiceGenerate, user: FrontDeskUser, db: DbSession) -> object:
    return billing_service.generate_invoice(db, body, user)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, _: FrontDeskUser, db: DbSession) -> object:
    return get_or_404(db, Invoice, invoice_id, "Invoice")


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceDetail)
def cancel_invoice(invoice_id: int, _: FrontDeskUser, db: DbSession) -> object:
    return billing_service.cancel_invoice(db, invoice_id)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    invoice_id: int, body: PaymentCreate, user: FrontDeskUser, db: DbSession
) -> object:
    return billing_service.record_payment(db, invoice_id, body, user)


@router.get("/payments", response_model=Page[PaymentListItem])
def list_payments(
    _: FrontDeskUser, db: DbSession, paging: Paging, invoice_id: int | None = None
) -> dict:
    return billing_service.list_payments(
        db, invoice_id=invoice_id, page=paging.page, page_size=paging.page_size
    )
