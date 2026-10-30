import uuid
from datetime import UTC, datetime
from typing import Any, Generic

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import User
from app.repositories.base import M, Repository, SearchField
from app.schemas.common import ListParams
from app.services import audit


class CRUDService(Generic[M]):
    """Default business logic for a resource. Subclasses override hooks for special rules."""

    def __init__(
        self,
        model: type[M],
        *,
        label: str | None = None,
        search_fields: tuple[SearchField, ...] = (),
        actor_field: str | None = None,
    ) -> None:
        self.model = model
        self.repo = Repository(model)
        self.label = label or model.__name__
        self.search_fields = search_fields
        # Column that records who created the row (e.g. created_by, marked_by).
        self.actor_field = actor_field

    # --- hooks -----------------------------------------------------------
    def list_query(self) -> Select:
        return select(self.model)

    def apply_filters(self, stmt: Select, filters: dict[str, Any]) -> Select:
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        return stmt

    def before_create(self, db: Session, values: dict[str, Any], actor: User) -> dict[str, Any]:
        return values

    def before_update(self, db: Session, obj: M, values: dict[str, Any], actor: User) -> dict[str, Any]:
        return values

    # --- operations ------------------------------------------------------
    def list(self, db: Session, params: ListParams, filters: dict[str, Any]) -> tuple[list[M], int]:
        stmt = self.apply_filters(self.list_query(), filters)
        return self.repo.list(db, params, stmt=stmt, search_fields=self.search_fields)

    def get(self, db: Session, id: uuid.UUID, *, for_update: bool = False) -> M:
        obj = self.repo.get(db, id, for_update=for_update)
        if obj is None:
            raise NotFoundError(f"{self.label} not found")
        return obj

    def create(self, db: Session, data: BaseModel, actor: User) -> M:
        values = data.model_dump()
        if self.actor_field:
            values[self.actor_field] = actor.id
        values = self.before_create(db, values, actor)
        obj = self.repo.create(db, values)
        audit.record(db, actor, "create", self.model.__tablename__, obj.id, values)
        db.commit()
        return obj

    def update(self, db: Session, id: uuid.UUID, data: BaseModel, actor: User) -> M:
        obj = self.get(db, id, for_update=True)
        values = self.before_update(db, obj, data.model_dump(exclude_unset=True), actor)
        if values:
            self.repo.update(db, obj, values)
            audit.record(db, actor, "update", self.model.__tablename__, obj.id, values)
        db.commit()
        return obj

    def delete(self, db: Session, id: uuid.UUID, actor: User) -> None:
        obj = self.get(db, id, for_update=True)
        if self.repo.soft_delete:
            obj.deleted_at = datetime.now(UTC)
            action = "archive"
        else:
            db.delete(obj)
            action = "delete"
        db.flush()
        audit.record(db, actor, action, self.model.__tablename__, id)
        db.commit()
