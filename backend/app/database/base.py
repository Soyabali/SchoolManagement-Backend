import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    MetaData,
    Numeric,
    String,
    Time,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names so Alembic can diff and drop them reliably.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Fetch server-generated values (id, timestamps, computed columns) via RETURNING
    # in the same round trip instead of lazy-loading them afterwards.
    __mapper_args__ = {"eager_defaults": True}
    type_annotation_map = {
        uuid.UUID: Uuid,
        datetime: DateTime(timezone=True),
        date: Date,
        time: Time,
        Decimal: Numeric(12, 2),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
        str: String(255),
    }


class UUIDPrimaryKeyMixin:
    # uuidv7() is native in PostgreSQL 18; time-ordered keys keep B-tree inserts local.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def choice_check(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """CHECK constraint used instead of a native ENUM, which is awkward to alter in migrations."""
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_valid")
