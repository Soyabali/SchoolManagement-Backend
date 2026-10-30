import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, inspect, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.exceptions import AppError
from app.database.base import Base
from app.schemas.common import ListParams

M = TypeVar("M", bound=Base)

SearchField = str | InstrumentedAttribute


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Repository(Generic[M]):
    """Generic data access for one model: get, paginated list, create, update, delete."""

    def __init__(self, model: type[M]) -> None:
        self.model = model
        self.column_names = {c.key for c in inspect(model).column_attrs}
        self.soft_delete = "deleted_at" in self.column_names

    def _column(self, field: SearchField) -> Any:
        return getattr(self.model, field) if isinstance(field, str) else field

    def get(self, db: Session, id: uuid.UUID, *, for_update: bool = False) -> M | None:
        stmt = select(self.model).where(self.model.id == id)
        if self.soft_delete:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).unique().scalar_one_or_none()

    def apply_search(self, stmt: Select, term: str | None, fields: tuple[SearchField, ...]) -> Select:
        if not term or not fields:
            return stmt
        pattern = f"%{escape_like(term)}%"
        return stmt.where(or_(*(self._column(f).ilike(pattern, escape="\\") for f in fields)))

    def apply_sort(self, stmt: Select, sort: str | None) -> Select:
        if sort:
            descending = sort.startswith("-")
            name = sort.lstrip("-")
            if name not in self.column_names:
                raise AppError(
                    f"Cannot sort by '{name}'",
                    details={"sortable": sorted(self.column_names)},
                )
            column = getattr(self.model, name)
            return stmt.order_by(column.desc() if descending else column.asc(), self.model.id)
        if "created_at" in self.column_names:
            return stmt.order_by(self.model.created_at.desc(), self.model.id.desc())
        return stmt

    def paginate(self, db: Session, stmt: Select, page: int, size: int) -> tuple[list[Any], int]:
        """Rows plus total count in ONE round trip (count(*) OVER () window)."""
        offset = (page - 1) * size
        rows = db.execute(
            stmt.add_columns(func.count().over().label("_total")).offset(offset).limit(size)
        ).unique().all()
        if rows:
            total = rows[0]._total
        elif offset == 0:
            total = 0
        else:  # page past the end: still report the real total
            total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        return list(rows), total

    def list(
        self,
        db: Session,
        params: ListParams,
        *,
        stmt: Select | None = None,
        search_fields: tuple[SearchField, ...] = (),
    ) -> tuple[list[M], int]:
        stmt = stmt if stmt is not None else select(self.model)
        if self.soft_delete:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        stmt = self.apply_search(stmt, params.search, search_fields)
        stmt = self.apply_sort(stmt, params.sort)
        rows, total = self.paginate(db, stmt, params.page, params.size)
        return [row[0] for row in rows], total

    def create(self, db: Session, values: dict[str, Any]) -> M:
        obj = self.model(**values)
        db.add(obj)
        db.flush()
        return obj

    def update(self, db: Session, obj: M, values: dict[str, Any]) -> M:
        for key, value in values.items():
            setattr(obj, key, value)
        db.flush()
        return obj
