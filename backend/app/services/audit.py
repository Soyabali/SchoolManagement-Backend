import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.context import request_context
from app.models import AuditLog, User

SECRET_KEYS = {"password", "new_password", "current_password", "password_hash", "token_hash",
               "refresh_token", "access_token", "raw_response"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k in SECRET_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def record(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    """Add an audit entry to the current transaction (committed with the change itself)."""
    ctx = request_context.get()
    db.add(
        AuditLog(
            user_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=jsonable_encoder(_scrub(changes)) if changes else None,
            ip_address=ctx.ip_address if ctx else None,
            user_agent=ctx.user_agent[:255] if ctx and ctx.user_agent else None,
        )
    )
