"""Password hashing (Argon2id) and JWT access tokens."""

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

# Argon2id with pwdlib's recommended parameters (OWASP-aligned).
password_hash = PasswordHash.recommended()

# Argon2id is memory-hard (~64 MiB per hash). Sync endpoints run in a 40-thread pool,
# so a login flood could demand ~2.5 GiB at once and OOM-kill the pod. Capping
# concurrent hashes bounds memory to ~4 x 64 MiB; excess requests simply queue.
# (Floods are also rate-limited at the Ingress - defence in depth.)
MAX_CONCURRENT_HASHES = 4
_hash_slots = threading.BoundedSemaphore(MAX_CONCURRENT_HASHES)

_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    with _hash_slots:
        return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    with _hash_slots:
        return password_hash.verify(password, hashed)


def burn_password_check(password: str) -> None:
    """Verify against a dummy hash so unknown e-mails take as long as wrong passwords.

    This prevents user enumeration through response-time differences.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password-for-timing")
    verify_password(password, _dummy_hash)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a token. Raises jwt.PyJWTError on any problem."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
