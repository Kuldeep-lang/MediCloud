"""Role-based access control matrix (see docs/architecture.md section 4.2).

Each role must be denied (403) outside its responsibilities, and every protected
endpoint must reject anonymous calls (401). Checks run before any lookups, so
non-existent IDs are fine here.
"""

import pytest

from app.models.enums import Role

FORBIDDEN = [
    # pharmacist: no billing, appointments, beds, users
    (Role.PHARMACIST, "GET", "/api/v1/invoices"),
    (Role.PHARMACIST, "GET", "/api/v1/appointments"),
    (Role.PHARMACIST, "GET", "/api/v1/beds"),
    (Role.PHARMACIST, "POST", "/api/v1/patients"),
    (Role.PHARMACIST, "GET", "/api/v1/dashboard/revenue"),
    # receptionist: no pharmacy inventory, no dispensing, no users, no revenue
    (Role.RECEPTIONIST, "GET", "/api/v1/medicines"),
    (Role.RECEPTIONIST, "POST", "/api/v1/prescriptions/1/dispense"),
    (Role.RECEPTIONIST, "POST", "/api/v1/prescriptions"),
    (Role.RECEPTIONIST, "GET", "/api/v1/users"),
    (Role.RECEPTIONIST, "GET", "/api/v1/dashboard/revenue"),
    (Role.RECEPTIONIST, "GET", "/api/v1/system/status"),
    # doctor: no billing, no booking, no user admin, no stock changes
    (Role.DOCTOR, "GET", "/api/v1/invoices"),
    (Role.DOCTOR, "POST", "/api/v1/appointments"),
    (Role.DOCTOR, "GET", "/api/v1/users"),
    (Role.DOCTOR, "POST", "/api/v1/medicines/1/stock"),
    (Role.DOCTOR, "POST", "/api/v1/patients"),
    (Role.DOCTOR, "POST", "/api/v1/wards"),
]


@pytest.mark.parametrize(("role", "method", "path"), FORBIDDEN)
def test_role_is_forbidden(client, factory, role, method, path):
    headers = factory.headers(factory.user(role))
    response = client.request(method, path, headers=headers, json={})
    assert response.status_code == 403, f"{role} {method} {path} -> {response.status_code}"


PROTECTED = [
    ("GET", "/api/v1/patients"),
    ("GET", "/api/v1/doctors"),
    ("GET", "/api/v1/appointments"),
    ("GET", "/api/v1/beds/occupancy"),
    ("GET", "/api/v1/medicines"),
    ("GET", "/api/v1/invoices"),
    ("GET", "/api/v1/dashboard/summary"),
    ("POST", "/api/v1/admissions"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_anonymous_requests_are_rejected(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


@pytest.mark.parametrize(
    ("role", "path"),
    [
        (Role.ADMIN, "/api/v1/users"),
        (Role.RECEPTIONIST, "/api/v1/invoices"),
        (Role.PHARMACIST, "/api/v1/medicines"),
        (Role.DOCTOR, "/api/v1/medicines"),  # doctors read the formulary to prescribe
        (Role.DOCTOR, "/api/v1/patients"),
    ],
)
def test_role_is_allowed(client, factory, role, path):
    headers = factory.headers(factory.user(role))
    assert client.get(path, headers=headers).status_code == 200


def test_doctor_without_profile_cannot_list_appointments(client, factory):
    headers = factory.headers(factory.user(Role.DOCTOR))  # not linked to a doctor row
    assert client.get("/api/v1/appointments", headers=headers).status_code == 403
