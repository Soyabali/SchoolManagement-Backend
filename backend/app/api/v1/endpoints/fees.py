import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.core.exceptions import NotFoundError
from app.models import Discount, FeeCategory, FeePayment, FeeStructure, PaymentTransaction, Scholarship, StudentFee
from app.schemas.common import ListParams, Page
from app.schemas.fee import (
    DiscountIn,
    DiscountRead,
    FeeAssignIn,
    FeeAssignResult,
    FeeCategoryIn,
    FeeCategoryRead,
    FeePaymentIn,
    FeePaymentRead,
    FeePaymentReceipt,
    FeeStructureIn,
    FeeStructureRead,
    PaymentHistoryRow,
    PaymentMethod,
    PaymentTransactionRead,
    PendingFeeReport,
    ScholarshipIn,
    ScholarshipRead,
    StudentFeeIn,
    StudentFeeRead,
)
from app.services import fees as fee_service
from app.services.base import CRUDService

TAG = "Fees"
router = APIRouter()
can_read = [require_permission("fees:read")]
can_write = [require_permission("fees:write")]


@router.post("/student-fees/assign", response_model=FeeAssignResult, status_code=status.HTTP_201_CREATED,
             tags=[TAG], summary="Assign a fee structure to students",
             description="Charges every student enrolled in the structure's class (optionally one section, or "
                         "a list of `student_ids`). Students already charged for that due date are skipped. "
                         "An optional discount and/or scholarship reduces each charge.",
             dependencies=can_write)
def assign_fees(payload: FeeAssignIn, db: DbSession, user: CurrentUser):
    return fee_service.assign(db, payload, user)


@router.post("/fee-payments", response_model=FeePaymentReceipt, status_code=status.HTTP_201_CREATED,
             tags=[TAG], summary="Record a fee payment",
             description="Partial payments are allowed; a payment larger than the balance is rejected. "
                         "Returns the receipt number and the remaining balance.",
             dependencies=can_write)
def record_payment(payload: FeePaymentIn, db: DbSession, user: CurrentUser):
    return fee_service.record_payment(db, payload, user)


@router.get("/fee-payments", response_model=Page[PaymentHistoryRow], tags=[TAG],
            summary="Payment history", description="`search` matches receipt number, admission number, name.",
            dependencies=can_read)
def payment_history(
    db: DbSession,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    student_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
    payment_method: PaymentMethod | None = None,
):
    return fee_service.payment_history(db, ListParams(page=page, size=size, search=search),
                                       student_id=student_id, date_from=date_from, date_to=date_to,
                                       payment_method=payment_method)


@router.get("/fee-payments/{payment_id}", response_model=FeePaymentRead, tags=[TAG],
            summary="Get one payment (receipt)", dependencies=can_read)
def get_payment(payment_id: uuid.UUID, db: DbSession):
    payment = db.get(FeePayment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    return FeePaymentRead.model_validate(payment)


@router.get("/fees/pending", response_model=PendingFeeReport, tags=[TAG],
            summary="Pending (unpaid / partly paid) fees report",
            description="Each row shows net amount, amount paid and balance. `total_outstanding` covers all "
                        "matching rows, not just this page.",
            dependencies=can_read)
def pending_fees(
    db: DbSession,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    class_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None, overdue_only: bool = False,
):
    return fee_service.pending_report(db, ListParams(page=page, size=size, search=search), class_id=class_id,
                                      section_id=section_id, student_id=student_id, overdue_only=overdue_only)


for resource in (
    Resource("/fee-categories", TAG, "fee category", "fees",
             CRUDService(FeeCategory, label="Fee category", search_fields=("name",)),
             FeeCategoryIn, FeeCategoryRead),
    Resource("/fee-structures", TAG, "fee structure", "fees",
             CRUDService(FeeStructure, label="Fee structure"), FeeStructureIn, FeeStructureRead,
             filters={"academic_session_id": uuid.UUID, "class_id": uuid.UUID, "fee_category_id": uuid.UUID,
                      "frequency": str},
             description="How much a class pays for a fee category in a session."),
    Resource("/discounts", TAG, "discount", "fees",
             CRUDService(Discount, label="Discount", search_fields=("name",)), DiscountIn, DiscountRead,
             filters={"is_active": bool}),
    Resource("/scholarships", TAG, "scholarship", "fees",
             CRUDService(Scholarship, label="Scholarship", search_fields=("name",)), ScholarshipIn,
             ScholarshipRead, filters={"is_active": bool, "academic_session_id": uuid.UUID}),
    Resource("/student-fees", TAG, "student fee", "fees",
             CRUDService(StudentFee, label="Student fee"), StudentFeeIn, StudentFeeRead,
             filters={"student_id": uuid.UUID, "fee_structure_id": uuid.UUID, "status": str, "due_date": date},
             description="Individual charges. Use POST /student-fees/assign to charge a whole class. "
                         "A fee with payments cannot be deleted (409)."),
    Resource("/payment-transactions", TAG, "payment gateway transaction", "fees",
             CRUDService(PaymentTransaction, label="Transaction", search_fields=("provider_reference",)),
             FeePaymentIn, PaymentTransactionRead,
             filters={"student_id": uuid.UUID, "status": str, "provider": str},
             operations=frozenset({"list", "get"}),
             description="Read-only log of online payment gateway transactions."),
):
    router.include_router(crud_router(resource))
