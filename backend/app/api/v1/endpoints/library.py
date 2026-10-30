import uuid

from fastapi import APIRouter, Query, status

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.models import BookCategory
from app.schemas.common import ListParams, Page
from app.schemas.library import (
    BookCategoryIn,
    BookCategoryRead,
    BookIn,
    BookIssueIn,
    BookIssueRead,
    BookRead,
    BookReturnIn,
    BookReturnResult,
)
from app.services.base import CRUDService
from app.services.library import BookIssueService
from app.services.people import BookService

TAG = "Library"
router = APIRouter()
issues = BookIssueService()


@router.post("/library/issues", response_model=BookIssueRead, status_code=status.HTTP_201_CREATED, tags=[TAG],
             summary="Issue a book to a student or staff member",
             description="Fails with 409 when no copies are available.",
             dependencies=[require_permission("library:write")])
def issue_book(payload: BookIssueIn, db: DbSession, user: CurrentUser):
    return BookIssueRead.model_validate(issues.issue(db, payload, user))


@router.post("/library/issues/{issue_id}/return", response_model=BookReturnResult, tags=[TAG],
             summary="Return a book", description="`condition: lost` removes the copy from the stock.",
             dependencies=[require_permission("library:write")])
def return_book(issue_id: uuid.UUID, payload: BookReturnIn, db: DbSession, user: CurrentUser):
    return issues.return_book(db, issue_id, payload, user)


@router.get("/library/issues", response_model=Page[BookIssueRead], tags=[TAG], summary="List book issues",
            dependencies=[require_permission("library:read")])
def list_issues(
    db: DbSession,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(issued|returned|lost)$"),
    student_id: uuid.UUID | None = None, staff_id: uuid.UUID | None = None, book_id: uuid.UUID | None = None,
    overdue: bool = Query(False, description="Only books still out past their due date"),
):
    filters = {k: v for k, v in {"status": status, "student_id": student_id, "staff_id": staff_id,
                                 "book_id": book_id, "overdue": overdue or None}.items() if v is not None}
    return issues.list_issues(db, ListParams(page=page, size=size), filters)


@router.get("/library/issues/{issue_id}", response_model=BookIssueRead, tags=[TAG], summary="Get a book issue",
            dependencies=[require_permission("library:read")])
def get_issue(issue_id: uuid.UUID, db: DbSession):
    return BookIssueRead.model_validate(issues.get(db, issue_id))


for resource in (
    Resource("/book-categories", TAG, "book category", "library",
             CRUDService(BookCategory, label="Book category", search_fields=("name",)),
             BookCategoryIn, BookCategoryRead),
    Resource("/books", TAG, "book", "library", BookService(), BookIn, BookRead,
             filters={"category_id": uuid.UUID, "author": str},
             description="`available_copies` is managed automatically by issues and returns."),
):
    router.include_router(crud_router(resource))
