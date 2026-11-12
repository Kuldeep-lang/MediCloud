from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas.user import LoginRequest, TokenResponse, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> dict:
    user = user_service.authenticate(db, body.email, body.password)
    if user is None:
        # Deliberately generic: never reveal whether the e-mail exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token, expires_in = create_access_token(user.id, user.role.value)
    return {"access_token": token, "expires_in": expires_in, "user": user}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> object:
    return user
