import math
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class InputSchema(Schema):
    # Unknown fields are rejected so typos do not silently do nothing.
    model_config = ConfigDict(extra="forbid")


class ReadSchema(Schema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


def Str(max_length: int, min_length: int = 1) -> Any:
    return Annotated[str, StringConstraints(min_length=min_length, max_length=max_length)]


Phone = Annotated[str, StringConstraints(pattern=r"^\+?[0-9][0-9\- ]{6,18}$")]
Url = Annotated[str, StringConstraints(max_length=500, pattern=r"^https?://\S+$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Marks = Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)]


def partial(model: type[BaseModel], name: str | None = None) -> type[BaseModel]:
    """Derive an update schema where every field is optional but keeps its constraints."""
    fields: dict[str, Any] = {}
    for field_name, info in model.model_fields.items():
        annotation = info.annotation
        if info.metadata:
            annotation = Annotated[(annotation, *info.metadata)]
        fields[field_name] = (annotation | None, Field(None, description=info.description))
    return create_model(name or model.__name__.replace("In", "") + "Update", __base__=InputSchema, **fields)


class ListParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number, starting at 1")
    size: int = Field(20, ge=1, le=100, description="Items per page (max 100)")
    sort: str | None = Field(
        None, max_length=50, description="Column to sort by; prefix with '-' for descending (e.g. -created_at)"
    )
    search: str | None = Field(None, max_length=100, description="Case-insensitive text search")


T = TypeVar("T")


class Page(Schema, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[Any], total: int, page: int, size: int) -> "Page[T]":
        return cls(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0)


class DateRange(BaseModel):
    date_from: date | None = None
    date_to: date | None = None


class Message(Schema):
    message: str
