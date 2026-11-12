"""Medicine inventory, stock ledger, alerts, prescriptions and dispensing."""

from datetime import timedelta

from sqlalchemy import select

from app.core.timeutils import local_today
from app.models import StockMovement
from app.models.enums import Role


def stock(client, headers, medicine_id, change, reason="restock"):
    return client.post(
        f"/api/v1/medicines/{medicine_id}/stock",
        headers=headers,
        json={"change_quantity": change, "reason": reason},
    )


def test_add_medicine_records_opening_stock(client, pharmacist_headers, db):
    response = client.post(
        "/api/v1/medicines",
        headers=pharmacist_headers,
        json={
            "code": "amx-500",
            "name": "Amoxicillin 500",
            "category": "Antibiotic",
            "unit_price": "6.50",
            "stock_quantity": 200,
            "reorder_level": 50,
            "expiry_date": (local_today() + timedelta(days=400)).isoformat(),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "AMX-500"
    assert body["is_low_stock"] is False
    ledger = db.scalars(select(StockMovement)).all()
    assert [(m.change_quantity, m.balance_after) for m in ledger] == [(200, 200)]


def test_stock_adjustments_are_ledgered(client, factory, pharmacist_headers):
    med = factory.medicine(stock=10)
    assert stock(client, pharmacist_headers, med.id, 40).json()["stock_quantity"] == 50
    assert (
        stock(client, pharmacist_headers, med.id, -5, "adjustment").json()["stock_quantity"] == 45
    )
    movements = client.get(
        f"/api/v1/medicines/{med.id}/movements", headers=pharmacist_headers
    ).json()
    assert [m["balance_after"] for m in movements["items"]] == [45, 50]


def test_invalid_stock_changes(client, factory, pharmacist_headers):
    med = factory.medicine(stock=5)
    assert stock(client, pharmacist_headers, med.id, -10, "adjustment").status_code == 400
    assert stock(client, pharmacist_headers, med.id, -1, "restock").status_code == 400
    assert stock(client, pharmacist_headers, med.id, 3, "expired").status_code == 400
    assert stock(client, pharmacist_headers, med.id, 0, "adjustment").status_code == 400


def test_alerts(client, factory, pharmacist_headers):
    low = factory.medicine(stock=5, reorder=10)
    soon = factory.medicine(expiry_days=10)
    expired = factory.medicine(expiry_days=-3)
    factory.medicine()  # healthy
    alerts = client.get("/api/v1/medicines/alerts", headers=pharmacist_headers).json()
    assert [m["id"] for m in alerts["low_stock"]] == [low.id]
    assert [m["id"] for m in alerts["expiring_soon"]] == [soon.id]
    assert [m["id"] for m in alerts["expired"]] == [expired.id]
    low_only = client.get(
        "/api/v1/medicines", headers=pharmacist_headers, params={"low_stock": True}
    ).json()
    assert low_only["total"] == 1


def prescribe(client, headers, patient_id, items, **extra):
    return client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json={"patient_id": patient_id, "items": items, **extra},
    )


def item(medicine_id, quantity=10):
    return {
        "medicine_id": medicine_id,
        "dosage": "500 mg",
        "frequency": "1-0-1",
        "duration_days": 5,
        "quantity": quantity,
    }


def test_doctor_prescribes_as_themselves(client, factory, doctor_ctx):
    doctor, headers = doctor_ctx
    med = factory.medicine()
    response = prescribe(
        client, headers, factory.patient().id, [item(med.id)], doctor_id=999
    )  # ignored for doctors
    assert response.status_code == 201
    assert response.json()["doctor_id"] == doctor.id
    assert response.json()["status"] == "pending"


def test_prescription_validation(client, factory, admin_headers, doctor_ctx):
    _, doctor_headers = doctor_ctx
    patient, med = factory.patient(), factory.medicine()
    inactive = factory.medicine(active=False)
    assert prescribe(client, admin_headers, patient.id, [item(med.id)]).status_code == 400
    assert (
        prescribe(client, doctor_headers, patient.id, [item(med.id), item(med.id)]).status_code
        == 400
    )
    assert prescribe(client, doctor_headers, patient.id, [item(inactive.id)]).status_code == 400
    assert prescribe(client, doctor_headers, patient.id, []).status_code == 422


def test_dispensing_decrements_stock_atomically(client, factory, doctor_ctx, pharmacist_headers):
    _, doctor_headers = doctor_ctx
    med_a, med_b = factory.medicine(stock=50), factory.medicine(stock=20)
    rx = prescribe(
        client, doctor_headers, factory.patient().id, [item(med_a.id, 10), item(med_b.id, 5)]
    ).json()
    dispensed = client.post(
        f"/api/v1/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers
    )
    assert dispensed.status_code == 200
    assert dispensed.json()["status"] == "dispensed"
    a = client.get(f"/api/v1/medicines/{med_a.id}", headers=pharmacist_headers).json()
    b = client.get(f"/api/v1/medicines/{med_b.id}", headers=pharmacist_headers).json()
    assert (a["stock_quantity"], b["stock_quantity"]) == (40, 15)
    again = client.post(f"/api/v1/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers)
    assert again.status_code == 400
    usage = client.get("/api/v1/medicines/usage", headers=pharmacist_headers).json()
    assert usage["daily"][-1]["quantity"] == 15
    assert usage["top_medicines"][0]["medicine_id"] == med_a.id


def test_insufficient_stock_changes_nothing(client, factory, doctor_ctx, pharmacist_headers):
    _, doctor_headers = doctor_ctx
    plenty, scarce = factory.medicine(stock=100), factory.medicine(stock=2)
    rx = prescribe(
        client, doctor_headers, factory.patient().id, [item(plenty.id, 10), item(scarce.id, 5)]
    ).json()
    response = client.post(f"/api/v1/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers)
    assert response.status_code == 400
    assert scarce.name in response.json()["detail"]
    untouched = client.get(f"/api/v1/medicines/{plenty.id}", headers=pharmacist_headers).json()
    assert untouched["stock_quantity"] == 100  # all-or-nothing transaction


def test_expired_medicine_cannot_be_dispensed(client, factory, doctor_ctx, pharmacist_headers, db):
    _, doctor_headers = doctor_ctx
    med = factory.medicine(stock=100)
    rx = prescribe(client, doctor_headers, factory.patient().id, [item(med.id)]).json()
    med.expiry_date = local_today() - timedelta(days=1)
    db.commit()
    response = client.post(f"/api/v1/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers)
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_prescription_visibility(client, factory, doctor_ctx, receptionist_headers):
    _, doctor_headers = doctor_ctx
    other_user = factory.user(Role.DOCTOR)
    factory.doctor(user=other_user)
    other_headers = factory.headers(other_user)
    rx = prescribe(
        client, doctor_headers, factory.patient().id, [item(factory.medicine().id)]
    ).json()
    assert client.get(f"/api/v1/prescriptions/{rx['id']}", headers=other_headers).status_code == 404
    assert (
        client.get(f"/api/v1/prescriptions/{rx['id']}", headers=receptionist_headers).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/prescriptions/{rx['id']}/dispense", headers=receptionist_headers
        ).status_code
        == 403
    )
