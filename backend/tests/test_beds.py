"""Wards, beds, allocation and discharge."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Admission
from app.models.enums import AdmissionStatus, WardType


def admit(client, headers, patient, bed_id, doctor_id=None):
    return client.post(
        "/api/v1/admissions",
        headers=headers,
        json={
            "patient_id": patient.id,
            "bed_id": bed_id,
            "admitting_doctor_id": doctor_id,
            "reason": "Observation after fall",
        },
    )


def test_admin_creates_ward_and_beds(client, admin_headers):
    ward = client.post(
        "/api/v1/wards",
        headers=admin_headers,
        json={
            "name": "Cardiac ICU",
            "ward_type": "icu",
            "floor": 3,
            "daily_rate": "9000.00",
        },
    )
    assert ward.status_code == 201
    ward_id = ward.json()["id"]
    bed = client.post(
        "/api/v1/beds", headers=admin_headers, json={"ward_id": ward_id, "bed_number": "cicu-01"}
    )
    assert bed.status_code == 201
    assert bed.json()["bed_number"] == "CICU-01"
    duplicate = client.post(
        "/api/v1/beds", headers=admin_headers, json={"ward_id": ward_id, "bed_number": "CICU-01"}
    )
    assert duplicate.status_code == 409


def test_admission_occupies_bed_and_discharge_frees_it(client, factory, receptionist_headers):
    ward = factory.ward(beds=2)
    patient, bed = factory.patient(), ward.beds[0]
    doctor = factory.doctor()
    admitted = admit(client, receptionist_headers, patient, bed.id, doctor.id)
    assert admitted.status_code == 201
    body = admitted.json()
    assert body["status"] == "admitted"
    assert body["ward_name"] == ward.name
    assert body["doctor_name"] == doctor.full_name

    beds = client.get(
        "/api/v1/beds", headers=receptionist_headers, params={"ward_id": ward.id}
    ).json()
    occupied = next(b for b in beds if b["id"] == bed.id)
    assert occupied["status"] == "occupied"
    assert occupied["current_patient_code"] == patient.patient_code

    discharged = client.post(
        f"/api/v1/admissions/{body['id']}/discharge",
        headers=receptionist_headers,
        json={"discharge_summary": "Stable, follow up in 1 week"},
    )
    assert discharged.status_code == 200
    assert discharged.json()["discharged_at"] is not None
    beds = client.get(
        "/api/v1/beds", headers=receptionist_headers, params={"status": "available"}
    ).json()
    assert {b["id"] for b in beds} == {ward.beds[0].id, ward.beds[1].id}
    again = client.post(
        f"/api/v1/admissions/{body['id']}/discharge", headers=receptionist_headers, json={}
    )
    assert again.status_code == 400


def test_occupied_bed_cannot_be_allocated_twice(client, factory, receptionist_headers):
    bed = factory.ward(beds=1).beds[0]
    assert admit(client, receptionist_headers, factory.patient(), bed.id).status_code == 201
    second = admit(client, receptionist_headers, factory.patient(), bed.id)
    assert second.status_code == 409


def test_patient_cannot_hold_two_beds(client, factory, receptionist_headers):
    ward = factory.ward(beds=2)
    patient = factory.patient()
    assert admit(client, receptionist_headers, patient, ward.beds[0].id).status_code == 201
    assert admit(client, receptionist_headers, patient, ward.beds[1].id).status_code == 409


def test_occupancy_summary(client, factory, receptionist_headers, admin_headers):
    general = factory.ward(beds=4)
    icu = factory.ward(ward_type=WardType.ICU, beds=2, rate="8000.00")
    admit(client, receptionist_headers, factory.patient(), icu.beds[0].id)
    client.patch(
        f"/api/v1/beds/{general.beds[3].id}", headers=admin_headers, json={"status": "maintenance"}
    )
    summary = client.get("/api/v1/beds/occupancy", headers=receptionist_headers).json()
    assert summary["overall"] == {
        "total": 6,
        "available": 4,
        "occupied": 1,
        "maintenance": 1,
        "occupancy_rate": 16.7,
    }
    assert summary["by_ward_type"]["icu"]["occupied"] == 1
    assert summary["by_ward_type"]["icu"]["occupancy_rate"] == 50.0


def test_occupied_bed_cannot_go_to_maintenance(
    client, factory, receptionist_headers, admin_headers
):
    bed = factory.ward(beds=1).beds[0]
    admit(client, receptionist_headers, factory.patient(), bed.id)
    response = client.patch(
        f"/api/v1/beds/{bed.id}", headers=admin_headers, json={"status": "maintenance"}
    )
    assert response.status_code == 400


def test_maintenance_bed_cannot_be_allocated(client, factory, receptionist_headers, admin_headers):
    bed = factory.ward(beds=1).beds[0]
    client.patch(f"/api/v1/beds/{bed.id}", headers=admin_headers, json={"status": "maintenance"})
    assert admit(client, receptionist_headers, factory.patient(), bed.id).status_code == 409


def test_doctor_can_discharge_pharmacist_cannot_view(
    client, factory, receptionist_headers, doctor_ctx, pharmacist_headers
):
    _, doctor_headers = doctor_ctx
    bed = factory.ward(beds=1).beds[0]
    admission = admit(client, receptionist_headers, factory.patient(), bed.id).json()
    assert (
        client.post(
            f"/api/v1/admissions/{admission['id']}/discharge", headers=doctor_headers, json={}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/beds", headers=pharmacist_headers).status_code == 403


def test_database_enforces_status_discharge_consistency(factory, db):
    bed = factory.ward(beds=1).beds[0]
    db.add(
        Admission(
            patient_id=factory.patient().id,
            bed_id=bed.id,
            reason="x",
            status=AdmissionStatus.DISCHARGED,
        )
    )  # discharged without a timestamp
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
