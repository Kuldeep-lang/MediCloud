"""Appointment booking rules, rescheduling, cancellation and status tracking."""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.timeutils import local_today, now_utc
from app.models import Appointment
from app.models.enums import AppointmentStatus
from tests.conftest import local_at, tomorrow_iso


@pytest.fixture
def setup(factory):
    return factory.doctor(), factory.patient()


def book(client, headers, patient, doctor, when, duration=15):
    return client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_id": patient.id,
            "doctor_id": doctor.id,
            "scheduled_at": when,
            "duration_minutes": duration,
            "reason": "Check-up",
        },
    )


def test_book_appointment(client, receptionist_headers, setup):
    doctor, patient = setup
    response = book(client, receptionist_headers, patient, doctor, tomorrow_iso(10))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["patient_code"] == patient.patient_code
    assert body["doctor_name"] == doctor.full_name
    # Naive input is interpreted as hospital time (IST, UTC+05:30) and stored in UTC.
    assert body["scheduled_at"].endswith("04:30:00Z")


def test_outside_working_hours_is_rejected(client, receptionist_headers, setup):
    doctor, patient = setup
    response = book(client, receptionist_headers, patient, doctor, tomorrow_iso(21))
    assert response.status_code == 400
    assert "working hours" in response.json()["detail"]


def test_past_time_is_rejected(client, receptionist_headers, setup):
    doctor, patient = setup
    past = (now_utc() - timedelta(hours=2)).isoformat()
    assert book(client, receptionist_headers, patient, doctor, past).status_code == 400


def test_double_booking_and_overlap_are_rejected(client, factory, receptionist_headers, setup):
    doctor, patient = setup
    assert (
        book(
            client, receptionist_headers, patient, doctor, tomorrow_iso(10), duration=30
        ).status_code
        == 201
    )
    other_patient = factory.patient()
    same_slot = book(client, receptionist_headers, other_patient, doctor, tomorrow_iso(10))
    overlapping = book(client, receptionist_headers, other_patient, doctor, tomorrow_iso(10, 15))
    assert same_slot.status_code == overlapping.status_code == 409
    adjacent = book(client, receptionist_headers, other_patient, doctor, tomorrow_iso(10, 30))
    assert adjacent.status_code == 201


def test_patient_cannot_be_in_two_places(client, factory, receptionist_headers, setup):
    doctor, patient = setup
    other_doctor = factory.doctor()
    assert book(client, receptionist_headers, patient, doctor, tomorrow_iso(11)).status_code == 201
    clash = book(client, receptionist_headers, patient, other_doctor, tomorrow_iso(11))
    assert clash.status_code == 409
    assert "patient" in clash.json()["detail"].lower()


def test_reschedule_and_reassign(client, factory, receptionist_headers, setup):
    doctor, patient = setup
    appt = book(client, receptionist_headers, patient, doctor, tomorrow_iso(9)).json()
    new_doctor = factory.doctor()
    response = client.patch(
        f"/api/v1/appointments/{appt['id']}",
        headers=receptionist_headers,
        json={"scheduled_at": tomorrow_iso(15), "doctor_id": new_doctor.id},
    )
    assert response.status_code == 200
    assert response.json()["doctor_id"] == new_doctor.id
    # Rescheduling into its own previous slot must not conflict with itself.
    again = client.patch(
        f"/api/v1/appointments/{appt['id']}",
        headers=receptionist_headers,
        json={"duration_minutes": 30},
    )
    assert again.status_code == 200


def test_cancel_frees_the_slot(client, factory, receptionist_headers, setup):
    doctor, patient = setup
    appt = book(client, receptionist_headers, patient, doctor, tomorrow_iso(12)).json()
    cancelled = client.post(
        f"/api/v1/appointments/{appt['id']}/cancel",
        headers=receptionist_headers,
        json={"reason": "Patient request"},
    )
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancellation_reason"] == "Patient request"
    assert (
        book(client, receptionist_headers, factory.patient(), doctor, tomorrow_iso(12)).status_code
        == 201
    )
    # A cancelled appointment cannot be cancelled or rescheduled again.
    assert (
        client.post(
            f"/api/v1/appointments/{appt['id']}/cancel", headers=receptionist_headers, json={}
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/appointments/{appt['id']}",
            headers=receptionist_headers,
            json={"scheduled_at": tomorrow_iso(16)},
        ).status_code
        == 400
    )


def test_doctor_completes_visit_with_diagnosis(client, factory, doctor_ctx):
    doctor, headers = doctor_ctx
    appt = factory.appointment(factory.patient(), doctor)
    response = client.patch(
        f"/api/v1/appointments/{appt.id}/status",
        headers=headers,
        json={
            "status": "completed",
            "diagnosis": "Viral fever",
            "notes": "Paracetamol, fluids",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["diagnosis"] == "Viral fever"
    # Completed is terminal.
    reopen = client.patch(
        f"/api/v1/appointments/{appt.id}/status", headers=headers, json={"status": "confirmed"}
    )
    assert reopen.status_code == 400


def test_receptionist_confirms_but_cannot_complete(client, factory, receptionist_headers):
    appt = factory.appointment(factory.patient(), factory.doctor())
    url = f"/api/v1/appointments/{appt.id}/status"
    assert (
        client.patch(url, headers=receptionist_headers, json={"status": "confirmed"}).status_code
        == 200
    )
    assert (
        client.patch(url, headers=receptionist_headers, json={"status": "completed"}).status_code
        == 400
    )


def test_future_visit_cannot_be_completed(client, factory, doctor_ctx):
    doctor, headers = doctor_ctx
    future = local_at(local_today() + timedelta(days=3), 10)
    appt = factory.appointment(factory.patient(), doctor, when=future)
    response = client.patch(
        f"/api/v1/appointments/{appt.id}/status", headers=headers, json={"status": "completed"}
    )
    assert response.status_code == 400


def test_doctors_only_see_their_own_appointments(client, factory, doctor_ctx):
    doctor, headers = doctor_ctx
    mine = factory.appointment(factory.patient(), doctor)
    theirs = factory.appointment(factory.patient(), factory.doctor())
    listing = client.get(
        "/api/v1/appointments", headers=headers, params={"doctor_id": theirs.doctor_id}
    ).json()
    assert [a["id"] for a in listing["items"]] == [mine.id]  # filter is overridden
    assert client.get(f"/api/v1/appointments/{theirs.id}", headers=headers).status_code == 404


def test_filter_by_date(client, factory, admin_headers):
    doctor, patient = factory.doctor(), factory.patient()
    yesterday = local_today() - timedelta(days=1)
    factory.appointment(patient, doctor, when=local_at(yesterday, 10))
    factory.appointment(patient, doctor, when=local_at(yesterday - timedelta(days=1), 10))
    result = client.get(
        "/api/v1/appointments", headers=admin_headers, params={"date": yesterday.isoformat()}
    ).json()
    assert result["total"] == 1


def test_database_blocks_double_booking_even_without_the_service(factory, db):
    """Partial unique index: a race that slips past the service still cannot double-book."""
    doctor, when = factory.doctor(), local_at(local_today() + timedelta(days=2), 10)
    factory.appointment(factory.patient(), doctor, when=when)
    db.add(
        Appointment(
            patient_id=factory.patient().id,
            doctor_id=doctor.id,
            scheduled_at=when,
            duration_minutes=15,
            status=AppointmentStatus.CONFIRMED,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
