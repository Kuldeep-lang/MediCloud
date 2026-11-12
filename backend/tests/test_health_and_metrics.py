"""Probes, Prometheus metrics and system endpoints."""

from app.models.enums import Role


def test_liveness(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_readiness_checks_database(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_metrics_use_route_templates_not_raw_ids(client):
    client.get("/api/v1/patients/12345")  # 401, but still counted
    client.get("/this/path/does/not/exist")
    body = client.get("/metrics").text
    assert 'route="/api/v1/patients/{patient_id}"' in body
    assert 'route="/api/v1/patients/12345"' not in body  # bounded label cardinality
    assert 'route="unmatched"' in body
    assert "http_request_duration_seconds_bucket" in body
    assert "medicloud_db_up 1.0" in body
    assert "medicloud_build_info" in body


def test_public_info_exposes_no_secrets(client):
    data = client.get("/api/v1/system/info").json()
    assert data["currency"] == "INR"
    assert data["timezone"] == "Asia/Kolkata"
    assert not any("secret" in key or "password" in key for key in data)


def test_system_status_is_admin_only(client, factory, admin_headers):
    assert client.get("/api/v1/system/status").status_code == 401
    receptionist = factory.headers(factory.user(Role.RECEPTIONIST))
    assert client.get("/api/v1/system/status", headers=receptionist).status_code == 403
    data = client.get("/api/v1/system/status", headers=admin_headers).json()
    assert data["database"]["status"] == "up"
    assert data["hostname"]
    assert data["uptime_seconds"] >= 0


def test_openapi_docs_served_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
