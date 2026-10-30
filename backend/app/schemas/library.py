import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, computed_field, model_validator

from app.schemas.common import InputSchema, Money, ReadSchema, Schema, Str


class BookCategoryIn(InputSchema):
    name: Str(100)
    description: str | None = Field(None, max_length=1000)


class BookCategoryRead(BookCategoryIn, ReadSchema):
    pass


class BookIn(InputSchema):
    title: Str(255)
    author: Str(255) | None = None
    isbn: str | None = Field(None, pattern=r"^[0-9Xx\-]{10,17}$")
    category_id: uuid.UUID | None = None
    publisher: Str(255) | None = None
    edition: Str(50) | None = None
    publication_year: int | None = Field(None, ge=1400, le=2100)
    total_copies: int = Field(1, ge=0, le=10000)
    shelf_location: Str(50) | None = None


class BookRead(BookIn, ReadSchema):
    available_copies: int


class BookIssueIn(InputSchema):
    book_id: uuid.UUID
    student_id: uuid.UUID | None = None
    staff_id: uuid.UUID | None = None
    issue_date: date = Field(default_factory=date.today)
    due_date: date

    @model_validator(mode="after")
    def _checks(self):
        if (self.student_id is None) == (self.staff_id is None):
            raise ValueError("provide exactly one of student_id or staff_id")
        if self.due_date < self.issue_date:
            raise ValueError("due_date must not be before issue_date")
        return self


class BookIssueRead(ReadSchema):
    book_id: uuid.UUID
    student_id: uuid.UUID | None
    staff_id: uuid.UUID | None
    issued_by: uuid.UUID | None
    issue_date: date
    due_date: date
    status: str

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return self.status == "issued" and self.due_date < date.today()


class BookReturnIn(InputSchema):
    return_date: date = Field(default_factory=date.today)
    condition: Literal["good", "damaged", "lost"] = "good"
    fine_amount: Money = Decimal("0")
    remarks: Str(255) | None = None


class BookReturnRead(ReadSchema):
    book_issue_id: uuid.UUID
    return_date: date
    fine_amount: Decimal
    condition: str
    received_by: uuid.UUID | None
    remarks: str | None


class BookReturnResult(Schema):
    issue: BookIssueRead
    book_return: BookReturnRead
    overdue_days: int
