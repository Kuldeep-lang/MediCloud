"""Doctor management, schedules and availability."""

from datetime import timedelta

from app.core.timeutils import local_today
from app.models.enums import Role
from tests.conftest import tomorrow_iso


def doctor_payload(department_id: int, **overrides) -> dict:
    return {
        "first_name": "Nikhil",
        "last_name": "Bose",
        "specialization": "Cardiology",
        "department_id": department_id,
        "license_number": "nmc-2019-555",
        "email": "Nikhil.Bose@test.medicloud.demo",
        "phone": "+91 9876501234",
        "consultation_fee": "900.00",
        "years_experience": 8,
        "schedules": [
            {"day_of_week": 0, "start_time": "09:00", "end_time": "13:00"},
            {"day_of_week": 0, "start_time": "14:00", "end_time": "17:00", "slot_minutes": 20},
        ],
    } | overrides


def test_admin_adds_doctor_with_schedule(client, factory, admin_headers):
    dept = factory.department()
    response = client.post("/api/v1/doctors", headers=admin_headers, json=doctor_payload(dept.id))
    assert response.status_code == 201
    body = response.json()
    assert body["license_number"] == "NMC-2019-555"  # normalised to upper case
    assert body["email"] == "nikhil.bose@test.medicloud.demo"
    assert body["full_name"] == "Dr. Nikhil Bose"
    assert body["department_name"] == dept.name
    assert body["consultation_fee"] == 900.0
    assert len(body["schedules"]) == 2


def test_duplicate_licence_is_rejected(client, factory, admin_headers):
    dept = factory.department()
    assert (
        client.post(
            "/api/v1/doctors", headers=admin_headers, json=doctor_payload(dept.id)
        ).status_code
        == 201
    )
    again = client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json=doctor_payload(dept.id, email="other@test.medicloud.demo"),
    )
    assert again.status_code == 409


def test_overlapping_schedule_blocks_are_rejected(client, factory, admin_headers):
    dept = factory.department()
    payload = doctor_payload(
        dept.id,
        schedules=[
            {"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 1, "start_time": "11:00", "end_time": "13:00"},
        ],
    )
    response = client.post("/api/v1/doctors", headers=admin_headers, json=payload)
    assert response.status_code == 400
    assert "overlap" in response.json()["detail"]


def test_inactive_department_is_rejected(client, factory, admin_headers):
    dept = factory.department(active=False)
    response = client.post("/api/v1/doctors", headers=admin_headers, json=doctor_payload(dept.id))
    assert response.status_code == 400


def test_removing_a_doctor_deactivates_it(client, factory, admin_headers):
    doctor = factory.doctor()
    assert client.delete(f"/api/v1/doctors/{doctor.id}", headers=admin_headers).status_code == 200
    active = client.get("/api/v1/doctors", headers=admin_headers).json()
    assert active["total"] == 0
    everyone = client.get(
        "/api/v1/doctors", headers=admin_headers, params={"include_inactive": True}
    ).json()
    assert everyone["items"][0]["is_active"] is False


def test_filter_doctors_by_department(client, factory, admin_headers):
    cardio, neuro = factory.department(), factory.department()
    factory.doctor(department=cardio)
    factory.doctor(department=neuro)
    result = client.get(
        "/api/v1/doctors", headers=admin_headers, params={"department_id": cardio.id}
    ).json()
    assert result["total"] == 1
    assert result["items"][0]["department_id"] == cardio.id


def test_doctor_edits_only_own_schedule(client, factory, doctor_ctx):
    doctor, headers = doctor_ctx
    other = factory.doctor()
    new_schedule = [{"day_of_week": 2, "start_time": "10:00", "end_time": "12:00"}]
    own = client.put(f"/api/v1/doctors/{doctor.id}/schedules", headers=headers, json=new_schedule)
    assert own.status_code == 200
    assert [s["day_of_week"] for s in own.json()] == [2]
    foreign = client.put(
        f"/api/v1/doctors/{other.id}/schedules", headers=headers, json=new_schedule
    )
    assert foreign.status_code == 403


def test_availability_marks_booked_slots(client, factory, receptionist_headers):
    doctor = factory.doctor()
    patient = factory.patient()
    booked = client.post(
        "/api/v1/appointments",
        headers=receptionist_headers,
        json={
            "patient_id": patient.id,
            "doctor_id": doctor.id,
            "scheduled_at": tomorrow_iso(10),
        },
    )
    assert booked.status_code == 201
    day = (local_today() + timedelta(days=1)).isoformat()
    slots = client.get(
        f"/api/v1/doctors/{doctor.id}/availability",
        headers=receptionist_headers,
        params={"date": day},
    ).json()
    assert len(slots) == 48  # 08:00-20:00 in 15-minute slots
    by_time = {s["start"][11:16]: s["available"] for s in slots}
    assert by_time["10:00"] is False
    assert by_time["10:15"] is True


def test_linking_a_non_doctor_account_is_rejected(client, factory, admin_headers):
    dept = factory.department()
    pharmacist = factory.user(Role.PHARMACIST)
    response = client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json=doctor_payload(dept.id, user_id=pharmacist.id),
    )
    assert response.status_code == 400
