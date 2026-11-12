from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, DbSession, Paging
from app.models import User
from app.models.enums import Role
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service
from app.services.common import get_or_404

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
def list_users(
    _: AdminUser,
    db: DbSession,
    paging: Paging,
    role: Role | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    return user_service.list_users(
        db, role=role, search=search, page=paging.page, page_size=paging.page_size
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: AdminUser, db: DbSession) -> object:
    return user_service.create_user(db, body)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession) -> object:
    user = get_or_404(db, User, user_id, "User")
    return user_service.update_user(db, user, body, admin)


@router.delete("/{user_id}", response_model=UserOut)
def deactivate_user(user_id: int, admin: AdminUser, db: DbSession) -> object:
    user = get_or_404(db, User, user_id, "User")
    return user_service.update_user(db, user, UserUpdate(is_active=False), admin)
