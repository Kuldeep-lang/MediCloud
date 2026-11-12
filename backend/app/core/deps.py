"""FastAPI dependencies: DB session, authentication, role-based authorisation, paging."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import Role

bearer_scheme = HTTPBearer(auto_error=False, description="JWT from POST /api/v1/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """Dependency factory: allow only the given roles (enforced server-side)."""
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return dependency


# Role groups used across routers (see the role matrix in docs/architecture.md section 4.2).
ADMIN = (Role.ADMIN,)
ALL_STAFF = (Role.ADMIN, Role.DOCTOR, Role.RECEPTIONIST, Role.PHARMACIST)
CLINICAL_DESK = (Role.ADMIN, Role.DOCTOR, Role.RECEPTIONIST)
FRONT_DESK = (Role.ADMIN, Role.RECEPTIONIST)
PHARMACY = (Role.ADMIN, Role.PHARMACIST)
PRESCRIBERS = (Role.ADMIN, Role.DOCTOR)

AdminUser = Annotated[User, Depends(require_roles(*ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(*ALL_STAFF))]
ClinicalDeskUser = Annotated[User, Depends(require_roles(*CLINICAL_DESK))]
FrontDeskUser = Annotated[User, Depends(require_roles(*FRONT_DESK))]
PharmacyUser = Annotated[User, Depends(require_roles(*PHARMACY))]
PrescriberUser = Annotated[User, Depends(require_roles(*PRESCRIBERS))]


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page = page
        self.page_size = page_size


Paging = Annotated[PageParams, Depends()]


def scoped_doctor_id(user: User, requested: int | None = None) -> int | None:
    """Doctors may only see their own records; other roles may filter freely."""
    if user.role == Role.DOCTOR:
        if user.doctor_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not linked to a doctor profile")
        return user.doctor_id
    return requested
