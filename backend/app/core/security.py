import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

settings = get_settings()
password_hasher = PasswordHash.recommended()  # Argon2id

# Verified against when the email is unknown, so response time does not reveal
# whether an account exists.
_DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> tuple[bool, str | None]:
    """Returns (valid, new_hash); new_hash is set when the stored hash needs upgrading."""
    if password_hash is None:
        password_hasher.verify(password, _DUMMY_HASH)
        return False, None
    return password_hasher.verify_and_update(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    lifetime = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid access token") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid access token")
    try:
        return uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthenticationError("Invalid access token") from exc


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, SHA-256 hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
