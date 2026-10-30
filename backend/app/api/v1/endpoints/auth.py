from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import CurrentUser, DbSession, OptionalUser
from app.schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    MeRead,
    RefreshIn,
    RegisterIn,
    TokenResponse,
    UserRead,
)
from app.services import auth as auth_service
from app.services.rbac import user_permissions

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             summary="Register a user",
             description="The **first** user ever registered becomes the admin (no login needed). "
                         "After that, only a logged-in user with `users:write` can register users, "
                         "and only an admin can create another admin.")
def register(payload: RegisterIn, db: DbSession, actor: OptionalUser):
    return UserRead.model_validate(auth_service.register(db, payload, actor))


@router.post("/login", response_model=TokenResponse, summary="Log in (JSON)",
             description="For the Flutter app and React dashboard. Returns an access token "
                         "(send as `Authorization: Bearer <token>`) and a refresh token.")
def login(payload: LoginIn, db: DbSession):
    return auth_service.login(db, payload.email, payload.password)


@router.post("/token", response_model=TokenResponse, summary="Log in (form, used by Swagger 'Authorize')",
             description="Same as /auth/login but takes form fields `username` (your email) and `password`.")
def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    return auth_service.login(db, form.username, form.password)


@router.post("/refresh", response_model=TokenResponse, summary="Get new tokens with a refresh token",
             description="Refresh tokens are single-use: each call returns a new pair and invalidates the "
                         "old refresh token. Re-using an old one signs the user out everywhere.")
def refresh(payload: RefreshIn, db: DbSession):
    return auth_service.refresh(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out (revoke a refresh token)")
def logout(payload: RefreshIn, db: DbSession):
    auth_service.logout(db, payload.refresh_token)


@router.get("/me", response_model=MeRead, summary="Current user with roles and permissions")
def me(user: CurrentUser, db: DbSession):
    return MeRead.model_validate({**UserRead.model_validate(user).model_dump(),
                                  "permissions": user_permissions(db, user)})


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Change your password",
             description="Signs you out of every other session (all refresh tokens are revoked).")
def change_password(payload: ChangePasswordIn, user: CurrentUser, db: DbSession):
    auth_service.change_password(db, user, payload.current_password, payload.new_password)
