"""Authentication: login, JWT validation, password hashing."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.models.enums import Role
from tests.conftest import DEFAULT_PASSWORD


def login(client, email, password=DEFAULT_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_returns_token_and_profile(client, factory, db):
    user = factory.user(Role.RECEPTIONIST, email="desk@test.medicloud.demo")
    response = login(client, "desk@test.medicloud.demo")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 60 * 60
    assert body["user"]["role"] == "receptionist"
    assert "hashed_password" not in body["user"]
    db.refresh(user)
    assert user.last_login_at is not None


def test_login_email_is_case_insensitive(client, factory):
    factory.user(Role.ADMIN, email="boss@test.medicloud.demo")
    assert login(client, "BOSS@Test.MediCloud.demo").status_code == 200


def test_wrong_password_and_unknown_email_get_identical_errors(client, factory):
    factory.user(Role.ADMIN, email="real@test.medicloud.demo")
    wrong_password = login(client, "real@test.medicloud.demo", "not-the-password")
    unknown_email = login(client, "ghost@test.medicloud.demo")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json() == unknown_email.json() == {"detail": "Incorrect email or password"}
    )


def test_inactive_user_cannot_login(client, factory):
    factory.user(Role.ADMIN, email="gone@test.medicloud.demo", active=False)
    assert login(client, "gone@test.medicloud.demo").status_code == 401


def test_login_validates_input(client):
    assert (
        client.post("/api/v1/auth/login", json={"email": "nope", "password": "x"}).status_code
        == 422
    )


def test_passwords_are_stored_as_argon2_hashes(factory):
    user = factory.user(Role.ADMIN)
    assert user.hashed_password.startswith("$argon2id$")
    assert DEFAULT_PASSWORD not in user.hashed_password


def test_me_requires_valid_token(client, factory):
    user = factory.user(Role.PHARMACIST)
    assert client.get("/api/v1/auth/me").status_code == 401
    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    ok = client.get("/api/v1/auth/me", headers=factory.headers(user))
    assert ok.status_code == 200
    assert ok.json()["email"] == user.email


def _token(user_id: int, *, key: str | None = None, expires_delta=timedelta(minutes=5), **extra):
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": "admin",
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
        **extra,
    }
    return jwt.encode(payload, key or settings.jwt_secret_key.get_secret_value(), "HS256")


def test_expired_token_is_rejected(client, factory):
    user = factory.user(Role.ADMIN)
    token = _token(user.id, expires_delta=timedelta(minutes=-1))
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_signed_with_another_key_is_rejected(client, factory):
    user = factory.user(Role.ADMIN)
    token = _token(user.id, key="an-attacker-controlled-key-that-is-long-enough!!")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_stops_working_when_user_is_deactivated(client, factory, db):
    user = factory.user(Role.ADMIN)
    headers = factory.headers(user)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_admin_user_management(client, factory, admin_headers):
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "New.User@test.medicloud.demo",
            "full_name": "New User",
            "role": "pharmacist",
            "password": "LongEnough1",
        },
    )
    assert created.status_code == 201
    assert created.json()["email"] == "new.user@test.medicloud.demo"
    duplicate = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "new.user@test.medicloud.demo",
            "full_name": "Again",
            "role": "pharmacist",
            "password": "LongEnough1",
        },
    )
    assert duplicate.status_code == 409
    short = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "x@test.medicloud.demo",
            "full_name": "Short",
            "role": "admin",
            "password": "short",
        },
    )
    assert short.status_code == 422

    user_id = created.json()["id"]
    assert (
        client.delete(f"/api/v1/users/{user_id}", headers=admin_headers).json()["is_active"]
        is False
    )
    assert login(client, "new.user@test.medicloud.demo", "LongEnough1").status_code == 401


def test_admin_cannot_deactivate_or_demote_self(client, factory):
    admin = factory.user(Role.ADMIN)
    headers = factory.headers(admin)
    assert client.delete(f"/api/v1/users/{admin.id}", headers=headers).status_code == 400
    demote = client.patch(f"/api/v1/users/{admin.id}", headers=headers, json={"role": "doctor"})
    assert demote.status_code == 400
