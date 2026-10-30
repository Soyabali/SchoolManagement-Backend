import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class BookCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "book_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Book(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "available_copies >= 0 AND available_copies <= total_copies", name="copies_range"
        ),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("book_categories.id", ondelete="SET NULL"), index=True
    )
    isbn: Mapped[str | None] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str | None] = mapped_column(String(255), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255))
    edition: Mapped[str | None] = mapped_column(String(50))
    publication_year: Mapped[int | None] = mapped_column(SmallInteger)
    total_copies: Mapped[int] = mapped_column(Integer, server_default="1")
    available_copies: Mapped[int] = mapped_column(Integer, server_default="1")
    shelf_location: Mapped[str | None] = mapped_column(String(50))


class BookIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "book_issues"
    __table_args__ = (
        # Borrowed by exactly one of: a student or a staff member.
        CheckConstraint("num_nonnulls(student_id, staff_id) = 1", name="one_borrower"),
        CheckConstraint("due_date >= issue_date", name="dates_ordered"),
        choice_check("status", ("issued", "returned", "lost")),
    )

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="RESTRICT"), index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    issue_date: Mapped[date]
    due_date: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="issued", index=True)


class BookReturn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "book_returns"
    __table_args__ = (
        CheckConstraint("fine_amount >= 0", name="fine_non_negative"),
        choice_check("condition", ("good", "damaged", "lost")),
    )

    book_issue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("book_issues.id", ondelete="CASCADE"), unique=True
    )
    return_date: Mapped[date]
    fine_amount: Mapped[Decimal] = mapped_column(server_default="0")
    condition: Mapped[str] = mapped_column(String(20), server_default="good")
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    remarks: Mapped[str | None] = mapped_column(String(255))
