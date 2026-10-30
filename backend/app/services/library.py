import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models import Book, BookIssue, BookReturn, Staff, Student, User
from app.schemas.common import ListParams, Page
from app.schemas.library import BookIssueIn, BookIssueRead, BookReturnIn, BookReturnRead, BookReturnResult
from app.services import audit
from app.services.base import CRUDService


class BookIssueService(CRUDService[BookIssue]):
    def __init__(self) -> None:
        super().__init__(BookIssue, label="Book issue")

    def apply_filters(self, stmt, filters):
        if filters.pop("overdue", None):
            stmt = stmt.where(BookIssue.status == "issued", BookIssue.due_date < date.today())
        return super().apply_filters(stmt, filters)

    def issue(self, db: Session, data: BookIssueIn, actor: User) -> BookIssue:
        book = db.scalar(select(Book).where(Book.id == data.book_id).with_for_update())
        if book is None:
            raise NotFoundError("Book not found")
        if book.available_copies <= 0:
            raise ConflictError("No copies of this book are available")
        if data.student_id and db.get(Student, data.student_id) is None:
            raise NotFoundError("Student not found")
        if data.staff_id and db.get(Staff, data.staff_id) is None:
            raise NotFoundError("Staff member not found")
        book.available_copies -= 1
        issue = BookIssue(**data.model_dump(), issued_by=actor.id)
        db.add(issue)
        db.flush()
        audit.record(db, actor, "issue_book", "book_issues", issue.id, data.model_dump())
        db.commit()
        return issue

    def return_book(self, db: Session, issue_id: uuid.UUID, data: BookReturnIn, actor: User) -> BookReturnResult:
        issue = db.scalar(select(BookIssue).where(BookIssue.id == issue_id).with_for_update())
        if issue is None:
            raise NotFoundError("Book issue not found")
        if issue.status != "issued":
            raise ConflictError(f"This book is already marked '{issue.status}'")
        if data.return_date < issue.issue_date:
            raise AppError("return_date cannot be before issue_date")
        book = db.scalar(select(Book).where(Book.id == issue.book_id).with_for_update())

        if data.condition == "lost":
            issue.status = "lost"
            book.total_copies -= 1  # the copy is gone; available count was already reduced at issue
        else:
            issue.status = "returned"
            book.available_copies += 1
        book_return = BookReturn(book_issue_id=issue.id, received_by=actor.id, **data.model_dump())
        db.add(book_return)
        db.flush()
        audit.record(db, actor, "return_book", "book_issues", issue.id, data.model_dump())
        db.commit()
        return BookReturnResult(
            issue=BookIssueRead.model_validate(issue),
            book_return=BookReturnRead.model_validate(book_return),
            overdue_days=max(0, (data.return_date - issue.due_date).days),
        )

    def list_issues(self, db: Session, params: ListParams, filters: dict) -> Page[BookIssueRead]:
        items, total = self.list(db, params, filters)
        return Page[BookIssueRead].build([BookIssueRead.model_validate(i) for i in items],
                                         total, params.page, params.size)
