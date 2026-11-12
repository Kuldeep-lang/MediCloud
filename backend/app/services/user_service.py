from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.security import burn_password_check, hash_password, verify_password
from app.core.timeutils import now_utc
from app.models import User
from app.models.enums import Role
from app.schemas.user import UserCreate, UserUpdate
from app.services.common import like_term, paginate


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user when credentials are valid and the account is active."""
    user = get_by_email(db, email)
    if user is None:
        burn_password_check(password)  # equalise timing for unknown e-mails
        return None
    if not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    user.last_login_at = now_utc()
    db.commit()
    return user


def list_users(
    db: Session,
    *,
    role: Role | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(User).order_by(User.full_name)
    if role:
        stmt = stmt.where(User.role == role)
    if search:
        term = like_term(search)
        stmt = stmt.where(
            or_(User.full_name.ilike(term, escape="\\"), User.email.ilike(term, escape="\\"))
        )
    return paginate(db, stmt, page, page_size)


def create_user(db: Session, data: UserCreate) -> User:
    if get_by_email(db, data.email):
        raise ConflictError("A user with this e-mail already exists")
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        role=data.role,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    return user


def update_user(db: Session, user: User, data: UserUpdate, acting_user: User) -> User:
    changes = data.model_dump(exclude_unset=True)
    if user.id == acting_user.id:
        if changes.get("is_active") is False:
            raise BusinessRuleError("You cannot deactivate your own account")
        if "role" in changes and changes["role"] != Role.ADMIN:
            raise BusinessRuleError("You cannot remove your own admin role")
    if "password" in changes:
        password = changes.pop("password")
        if password:
            user.hashed_password = hash_password(password)
    for key, value in changes.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    return user
