"""Invoices (manual and generated), double-billing protection and simulated payments."""

from datetime import timedelta

import pytest

from app.core.timeutils import now_utc
from app.models import Admission
from app.models.enums import AdmissionStatus, AppointmentStatus


@pytest.fixture
def billable_patient(client, factory, doctor_ctx, pharmacist_headers):
    """A patient with one completed visit, one dispensed prescription and a 3-day stay."""
    doctor, doctor_headers = doctor_ctx
    patient = factory.patient()
    factory.appointment(patient, doctor, status=AppointmentStatus.COMPLETED)
    med = factory.medicine(stock=100, price="12.50")
    rx = client.post(
        "/api/v1/prescriptions",
        headers=doctor_headers,
        json={
            "patient_id": patient.id,
            "items": [
                {"medicine_id": med.id, "dosage": "1 tab", "frequency": "1-0-1", "quantity": 10}
            ],
        },
    ).json()
    client.post(f"/api/v1/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers)
    ward = factory.ward(beds=1, rate="2000.00")
    factory.db.add(
        Admission(
            patient_id=patient.id,
            bed_id=ward.beds[0].id,
            reason="Observation",
            admitted_at=now_utc() - timedelta(days=3, hours=2),
            discharged_at=now_utc() - timedelta(hours=1),
            status=AdmissionStatus.DISCHARGED,
        )
    )
    factory.db.commit()
    return patient


def test_billable_preview(client, receptionist_headers, billable_patient):
    preview = client.get(
        "/api/v1/invoices/billable",
        headers=receptionist_headers,
        params={"patient_id": billable_patient.id},
    ).json()
    by_type = {i["item_type"]: i for i in preview["items"]}
    assert set(by_type) == {"consultation", "medicine", "room"}
    assert by_type["consultation"]["line_total"] == 800.0
    assert by_type["medicine"]["line_total"] == 125.0
    assert by_type["room"]["quantity"] == 4  # 3 days 1 hour -> 4 billable days
    assert preview["subtotal"] == 800 + 125 + 8000


def test_generate_invoice_and_prevent_double_billing(
    client, receptionist_headers, billable_patient
):
    response = client.post(
        "/api/v1/invoices/generate",
        headers=receptionist_headers,
        json={
            "patient_id": billable_patient.id,
            "discount": "25.00",
            "tax_percent": "5",
            "extra_items": [
                {"item_type": "diagnostic", "description": "Chest X-ray", "unit_price": "600.00"}
            ],
        },
    )
    assert response.status_code == 201
    invoice = response.json()
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["invoice_number"].endswith("-000001")
    assert len(invoice["items"]) == 4
    assert invoice["subtotal"] == 9525.0
    assert invoice["tax"] == 475.0  # 5% of (9525 - 25)
    assert invoice["total"] == 9975.0
    assert invoice["status"] == "unpaid"
    assert invoice["balance_due"] == 9975.0

    preview = client.get(
        "/api/v1/invoices/billable",
        headers=receptionist_headers,
        params={"patient_id": billable_patient.id},
    ).json()
    assert preview["items"] == []
    again = client.post(
        "/api/v1/invoices/generate",
        headers=receptionist_headers,
        json={"patient_id": billable_patient.id},
    )
    assert again.status_code == 400


def test_manual_invoice_rules(client, factory, receptionist_headers):
    patient = factory.patient()
    payload = {
        "patient_id": patient.id,
        "items": [
            {
                "item_type": "diagnostic",
                "description": "Blood test",
                "quantity": 2,
                "unit_price": "450.00",
            }
        ],
    }
    created = client.post("/api/v1/invoices", headers=receptionist_headers, json=payload)
    assert created.status_code == 201
    assert created.json()["total"] == 900.0
    too_much_discount = client.post(
        "/api/v1/invoices", headers=receptionist_headers, json=payload | {"discount": "1000.00"}
    )
    assert too_much_discount.status_code == 400
    assert (
        client.post(
            "/api/v1/invoices", headers=receptionist_headers, json=payload | {"items": []}
        ).status_code
        == 422
    )


def test_cannot_bill_someone_elses_appointment(client, factory, receptionist_headers):
    appt = factory.appointment(
        factory.patient(), factory.doctor(), status=AppointmentStatus.COMPLETED
    )
    response = client.post(
        "/api/v1/invoices",
        headers=receptionist_headers,
        json={
            "patient_id": factory.patient().id,
            "items": [
                {
                    "item_type": "consultation",
                    "description": "Consultation",
                    "unit_price": "100",
                    "appointment_id": appt.id,
                }
            ],
        },
    )
    assert response.status_code == 400


def _invoice(client, headers, patient_id, amount="1000.00"):
    return client.post(
        "/api/v1/invoices",
        headers=headers,
        json={
            "patient_id": patient_id,
            "items": [{"item_type": "other", "description": "Service", "unit_price": amount}],
        },
    ).json()


def pay(client, headers, invoice_id, amount, **extra):
    return client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=headers,
        json={"amount": amount, "method": "upi", **extra},
    )


def test_partial_then_full_payment(client, factory, receptionist_headers):
    invoice = _invoice(client, receptionist_headers, factory.patient().id)
    first = pay(client, receptionist_headers, invoice["id"], "400.00")
    assert first.status_code == 201
    assert first.json()["transaction_ref"].startswith("SIM-")  # simulated, no gateway
    state = client.get(f"/api/v1/invoices/{invoice['id']}", headers=receptionist_headers).json()
    assert (state["status"], state["amount_paid"], state["balance_due"]) == (
        "partially_paid",
        400.0,
        600.0,
    )
    assert pay(client, receptionist_headers, invoice["id"], "700.00").status_code == 400
    assert pay(client, receptionist_headers, invoice["id"], "600.00").status_code == 201
    state = client.get(f"/api/v1/invoices/{invoice['id']}", headers=receptionist_headers).json()
    assert state["status"] == "paid"
    assert len(state["payments"]) == 2
    assert pay(client, receptionist_headers, invoice["id"], "1.00").status_code == 400


def test_simulated_declined_payment(client, factory, receptionist_headers):
    invoice = _invoice(client, receptionist_headers, factory.patient().id)
    declined = pay(client, receptionist_headers, invoice["id"], "1000.00", simulate_failure=True)
    assert declined.json()["status"] == "failed"
    state = client.get(f"/api/v1/invoices/{invoice['id']}", headers=receptionist_headers).json()
    assert state["status"] == "unpaid"
    assert state["balance_due"] == 1000.0


def test_cancel_rules(client, factory, receptionist_headers):
    patient = factory.patient()
    unpaid = _invoice(client, receptionist_headers, patient.id)
    cancelled = client.post(f"/api/v1/invoices/{unpaid['id']}/cancel", headers=receptionist_headers)
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["balance_due"] == 0.0
    paid = _invoice(client, receptionist_headers, patient.id)
    pay(client, receptionist_headers, paid["id"], "100.00")
    assert (
        client.post(
            f"/api/v1/invoices/{paid['id']}/cancel", headers=receptionist_headers
        ).status_code
        == 400
    )


def test_cancelled_invoice_items_become_billable_again(
    client, receptionist_headers, billable_patient
):
    invoice = client.post(
        "/api/v1/invoices/generate",
        headers=receptionist_headers,
        json={"patient_id": billable_patient.id},
    ).json()
    client.post(f"/api/v1/invoices/{invoice['id']}/cancel", headers=receptionist_headers)
    preview = client.get(
        "/api/v1/invoices/billable",
        headers=receptionist_headers,
        params={"patient_id": billable_patient.id},
    ).json()
    assert len(preview["items"]) == 3


def test_payments_listing_and_search(client, factory, receptionist_headers):
    patient = factory.patient(first_name="Ishaan")
    invoice = _invoice(client, receptionist_headers, patient.id)
    pay(client, receptionist_headers, invoice["id"], "1000.00")
    payments = client.get("/api/v1/payments", headers=receptionist_headers).json()
    assert payments["items"][0]["invoice_number"] == invoice["invoice_number"]
    assert payments["items"][0]["patient_name"].startswith("Ishaan")
    found = client.get(
        "/api/v1/invoices", headers=receptionist_headers, params={"search": "ishaan"}
    ).json()
    assert found["total"] == 1


def test_manual_invoice_with_billable_lines_prevents_double_billing(
    client, receptionist_headers, billable_patient
):
    preview = client.get(
        "/api/v1/invoices/billable",
        headers=receptionist_headers,
        params={"patient_id": billable_patient.id},
    ).json()
    lines = [
        {
            k: item[k]
            for k in (
                "item_type",
                "description",
                "quantity",
                "unit_price",
                "appointment_id",
                "prescription_item_id",
                "admission_id",
            )
            if item.get(k) is not None
        }
        for item in preview["items"]
    ]
    body = {"patient_id": billable_patient.id, "items": lines}
    assert (
        client.post("/api/v1/invoices", headers=receptionist_headers, json=body).status_code == 201
    )
    again = client.post("/api/v1/invoices", headers=receptionist_headers, json=body)
    assert again.status_code == 400
    assert "billed" in again.json()["detail"]
