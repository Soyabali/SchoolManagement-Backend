from datetime import UTC, datetime

from sqlalchemy import exists, func, select, text, update
from sqlalchemy.orm import Session

from app.core.context import request_context
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    verify_password,
)
from app.models import RefreshToken, Role, User
from app.schemas.auth import RegisterIn, TokenResponse
from app.services import audit
from app.services.rbac import ADMIN_ROLE, has_permission, is_admin

INVALID_CREDENTIALS = "Invalid email or password"


def _now() -> datetime:
    return datetime.now(UTC)


def load_roles(db: Session, names: list[str]) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.name.in_(set(names)))).all()
    missing = set(names) - {r.name for r in roles}
    if missing:
        raise AppError("Unknown role(s)", details=sorted(missing))
    return list(roles)


def register(db: Session, data: RegisterIn, actor: User | None) -> User:
    # Serialise registrations so two simultaneous "first users" cannot both become admin.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('sms.user_registration'))"))
    is_first_user = not db.scalar(select(exists().where(User.id.is_not(None))))

    if is_first_user:
        role_names = [ADMIN_ROLE]
    else:
        if actor is None:
            raise AuthenticationError("Registration requires an administrator to be logged in")
        if not has_permission(db, actor, "users:write"):
            raise PermissionDeniedError("Missing permission: users:write")
        if not data.roles:
            raise AppError("At least one role is required", details={"field": "roles"})
        if ADMIN_ROLE in data.roles and not is_admin(actor):
            raise PermissionDeniedError("Only an admin can create another admin")
        role_names = list(data.roles)

    if db.scalar(select(exists().where(func.lower(User.email) == data.email))):
        raise ConflictError("A user with this email already exists")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        roles=load_roles(db, role_names),
    )
    db.add(user)
    db.flush()
    audit.record(db, actor or user, "register", "users", user.id,
                 {"email": user.email, "roles": role_names, "bootstrap_admin": is_first_user})
    db.commit()
    return user


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token, expires_in = create_access_token(user.id)
    raw, token_hash = generate_refresh_token()
    ctx = request_context.get()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_token_expiry(),
            ip_address=ctx.ip_address if ctx else None,
            user_agent=ctx.user_agent[:255] if ctx and ctx.user_agent else None,
        )
    )
    return TokenResponse(access_token=access_token, refresh_token=raw, expires_in=expires_in)


def login(db: Session, email: str, password: str) -> TokenResponse:
    user = db.scalar(
        select(User).where(func.lower(User.email) == email.lower(), User.deleted_at.is_(None))
    )
    valid, new_hash = verify_password(password, user.password_hash if user else None)
    if user is None or not valid:
        raise AuthenticationError(INVALID_CREDENTIALS)
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    if new_hash:
        user.password_hash = new_hash
    user.last_login_at = _now()
    tokens = _issue_tokens(db, user)
    audit.record(db, user, "login", "users", user.id)
    db.commit()
    return tokens


def refresh(db: Session, raw_token: str) -> TokenResponse:
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).with_for_update()
    )
    if token is None:
        raise AuthenticationError("Invalid refresh token")
    if token.revoked_at is not None:
        # A rotated-out token was presented again: assume it was stolen and end every session.
        revoke_all(db, token.user_id)
        audit.record(db, None, "refresh_token_reuse", "users", token.user_id)
        db.commit()
        raise AuthenticationError("Refresh token already used; all sessions have been signed out")
    if token.expires_at <= _now():
        raise AuthenticationError("Refresh token expired")
    user = db.get(User, token.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise AuthenticationError("Account is disabled")
    token.revoked_at = _now()
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def logout(db: Session, raw_token: str) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is not None and token.revoked_at is None:
        token.revoked_at = _now()
        audit.record(db, None, "logout", "users", token.user_id)
        db.commit()


def revoke_all(db: Session, user_id) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def change_password(db: Session, user: User, current: str, new: str) -> None:
    valid, _ = verify_password(current, user.password_hash)
    if not valid:
        raise AppError("Current password is incorrect")
    user.password_hash = hash_password(new)
    revoke_all(db, user.id)
    audit.record(db, user, "change_password", "users", user.id)
    db.commit()
