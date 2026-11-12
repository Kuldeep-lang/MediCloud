"""Dashboard KPIs and charts - all values computed live from the database."""

from datetime import timedelta

from app.core.timeutils import local_today
from app.models.enums import AppointmentStatus, Role
from tests.conftest import local_at


def test_summary_reflects_data_and_role(
    client, factory, admin_headers, receptionist_headers, pharmacist_headers, doctor_ctx
):
    doctor, doctor_headers = doctor_ctx
    patient = factory.patient()
    factory.patient()
    factory.medicine(stock=1, reorder=5)
    ward = factory.ward(beds=3)
    client.post(
        "/api/v1/admissions",
        headers=receptionist_headers,
        json={"patient_id": patient.id, "bed_id": ward.beds[0].id, "reason": "Fever"},
    )
    factory.appointment(patient, doctor, when=local_at(local_today(), 12))  # always "today"

    admin = client.get("/api/v1/dashboard/summary", headers=admin_headers).json()
    assert admin["total_patients"] == 2
    assert admin["total_doctors"] == 1
    assert admin["beds"] == {"total": 3, "available": 2, "occupied": 1, "maintenance": 0}
    assert admin["active_admissions"] == 1
    assert admin["low_stock_medicines"] == 1
    assert admin["monthly_revenue"] == 0.0
    assert admin["unpaid_invoices"] == 0

    desk = client.get("/api/v1/dashboard/summary", headers=receptionist_headers).json()
    assert "monthly_revenue" not in desk  # revenue is admin-only
    assert "unpaid_invoices" in desk

    pharmacy = client.get("/api/v1/dashboard/summary", headers=pharmacist_headers).json()
    assert "unpaid_invoices" not in pharmacy

    mine = client.get("/api/v1/dashboard/summary", headers=doctor_headers).json()
    assert mine["my_appointments_today"] == mine["appointments_today"] == 1


def test_admission_trend_is_zero_filled(client, factory, admin_headers, receptionist_headers):
    bed = factory.ward(beds=1).beds[0]
    client.post(
        "/api/v1/admissions",
        headers=receptionist_headers,
        json={"patient_id": factory.patient().id, "bed_id": bed.id, "reason": "Pain"},
    )
    trend = client.get(
        "/api/v1/dashboard/admissions-trend", headers=admin_headers, params={"days": 14}
    ).json()
    assert len(trend) == 14
    assert trend[-1]["date"] == local_today().isoformat()
    assert trend[-1]["admissions"] == 1
    assert sum(p["admissions"] for p in trend) == 1


def test_appointment_stats(client, factory, admin_headers):
    doctor, patient = factory.doctor(), factory.patient()
    yesterday = local_today() - timedelta(days=1)
    factory.appointment(
        patient, doctor, when=local_at(yesterday, 9), status=AppointmentStatus.COMPLETED
    )
    factory.appointment(
        patient, doctor, when=local_at(yesterday, 11), status=AppointmentStatus.CANCELLED
    )
    stats = client.get("/api/v1/dashboard/appointment-stats", headers=admin_headers).json()
    counts = {s["status"]: s["count"] for s in stats["by_status"]}
    assert counts == {"scheduled": 0, "confirmed": 0, "completed": 1, "cancelled": 1, "no_show": 0}
    day = next(d for d in stats["daily"] if d["date"] == yesterday.isoformat())
    assert day == {"date": yesterday.isoformat(), "total": 2, "completed": 1, "cancelled": 1}


def test_department_distribution_counts_distinct_patients(client, factory, admin_headers):
    dept = factory.department()
    doctor, patient = factory.doctor(department=dept), factory.patient()
    for days_ago in (1, 2):
        factory.appointment(
            patient, doctor, when=local_at(local_today() - timedelta(days=days_ago), 10)
        )
    result = client.get("/api/v1/dashboard/department-distribution", headers=admin_headers).json()
    assert result == [{"department": dept.name, "patients": 1}]


def test_revenue_by_month(client, factory, admin_headers, receptionist_headers):
    invoice = client.post(
        "/api/v1/invoices",
        headers=receptionist_headers,
        json={
            "patient_id": factory.patient().id,
            "items": [{"item_type": "other", "description": "Service", "unit_price": "1500.00"}],
        },
    ).json()
    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=receptionist_headers,
        json={"amount": "1500.00", "method": "cash"},
    )
    revenue = client.get(
        "/api/v1/dashboard/revenue", headers=admin_headers, params={"months": 3}
    ).json()
    assert len(revenue) == 3
    assert revenue[-1]["month"] == local_today().strftime("%Y-%m")
    assert revenue[-1]["revenue"] == 1500.0
    summary = client.get("/api/v1/dashboard/summary", headers=admin_headers).json()
    assert summary["monthly_revenue"] == 1500.0


def test_revenue_is_admin_only(client, factory):
    for role in (Role.RECEPTIONIST, Role.DOCTOR, Role.PHARMACIST):
        headers = factory.headers(factory.user(role))
        assert client.get("/api/v1/dashboard/revenue", headers=headers).status_code == 403
