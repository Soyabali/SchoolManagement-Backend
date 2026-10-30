from typing import Annotated

from fastapi import Depends
from fastapi.params import Depends as DependsParam
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models import Role, User
from app.services.rbac import has_permission

DbSession = Annotated[Session, Depends(get_db)]

# tokenUrl powers the "Authorize" button in Swagger UI (form login).
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().API_V1_PREFIX}/auth/token", auto_error=False
)


def _load_user(db: Session, token: str) -> User:
    user_id = decode_access_token(token)
    user = db.execute(
        select(User)
        .options(joinedload(User.roles).lazyload(Role.permissions))
        .where(User.id == user_id)
    ).unique().scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise AuthenticationError("User no longer exists")
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    return user


def get_current_user(db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")
    return _load_user(db, token)


def get_optional_user(
    db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User | None:
    return _load_user(db, token) if token else None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_permission(code: str) -> DependsParam:
    """Route dependency: 403 unless the current user's roles grant `code`."""

    def checker(db: DbSession, user: CurrentUser) -> User:
        if not has_permission(db, user, code):
            raise PermissionDeniedError(f"Missing permission: {code}")
        return user

    checker.__name__ = f"require_{code.replace(':', '_')}"
    return Depends(checker)
