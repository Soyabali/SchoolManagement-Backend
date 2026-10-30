import secrets
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models import (
    Discount,
    FeeCategory,
    FeePayment,
    FeeStructure,
    Scholarship,
    SchoolClass,
    Section,
    Student,
    StudentAdmission,
    StudentFee,
    User,
)
from app.repositories.base import Repository
from app.schemas.common import ListParams, Page
from app.schemas.fee import (
    FeeAssignIn,
    FeeAssignResult,
    FeePaymentIn,
    FeePaymentRead,
    FeePaymentReceipt,
    PaymentHistoryRow,
    PendingFeeReport,
    PendingFeeRow,
)
from app.services import audit

ZERO = Decimal("0.00")
OPEN_STATUSES = ("pending", "partial")
_payments_repo = Repository(FeePayment)


def _reduction(rule: Discount | Scholarship | None, amount: Decimal) -> Decimal:
    if rule is None:
        return ZERO
    if rule.discount_type == "percentage":
        return (amount * rule.value / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return rule.value


def _active_rule(db: Session, model, rule_id: uuid.UUID | None, label: str):
    if rule_id is None:
        return None
    rule = db.get(model, rule_id)
    if rule is None:
        raise NotFoundError(f"{label} not found")
    if not rule.is_active:
        raise AppError(f"{label} is not active")
    return rule


def assign(db: Session, data: FeeAssignIn, actor: User) -> FeeAssignResult:
    structure = db.get(FeeStructure, data.fee_structure_id)
    if structure is None:
        raise NotFoundError("Fee structure not found")

    if data.student_ids:
        student_ids = list(dict.fromkeys(data.student_ids))
        found = set(db.scalars(select(Student.id).where(
            Student.id.in_(student_ids), Student.deleted_at.is_(None))).all())
        if missing := [str(i) for i in student_ids if i not in found]:
            raise NotFoundError("Unknown student id(s)", details=missing)
    else:
        stmt = (select(StudentAdmission.student_id)
                .join(Section, Section.id == StudentAdmission.section_id)
                .join(Student, Student.id == StudentAdmission.student_id)
                .where(Section.class_id == structure.class_id,
                       StudentAdmission.academic_session_id == structure.academic_session_id,
                       StudentAdmission.status == "enrolled", Student.deleted_at.is_(None)))
        if data.section_id:
            stmt = stmt.where(StudentAdmission.section_id == data.section_id)
        student_ids = list(db.scalars(stmt).all())
        if not student_ids:
            raise AppError("No enrolled students found for this class/section in the fee structure's session")

    discount = _active_rule(db, Discount, data.discount_id, "Discount")
    scholarship = _active_rule(db, Scholarship, data.scholarship_id, "Scholarship")
    reduction = min(structure.amount, _reduction(discount, structure.amount) + _reduction(scholarship, structure.amount))

    rows = [{"student_id": sid, "fee_structure_id": structure.id, "due_date": data.due_date,
             "amount": structure.amount, "discount_amount": reduction,
             "discount_id": data.discount_id, "scholarship_id": data.scholarship_id}
            for sid in student_ids]
    created = db.scalars(
        insert(StudentFee).values(rows)
        .on_conflict_do_nothing(index_elements=["student_id", "fee_structure_id", "due_date"])
        .returning(StudentFee.id)
    ).all()
    audit.record(db, actor, "assign_fees", "fee_structures", structure.id,
                 {"due_date": data.due_date, "students": len(rows), "created": len(created)})
    db.commit()
    return FeeAssignResult(
        fee_structure_id=structure.id, due_date=data.due_date, amount=structure.amount,
        discount_amount=reduction, net_amount=structure.amount - reduction,
        created=len(created), skipped_existing=len(rows) - len(created),
    )


def _paid(db: Session, student_fee_id: uuid.UUID) -> Decimal:
    return db.scalar(select(func.coalesce(func.sum(FeePayment.amount), ZERO))
                     .where(FeePayment.student_fee_id == student_fee_id))


def record_payment(db: Session, data: FeePaymentIn, actor: User) -> FeePaymentReceipt:
    # Row lock: two cashiers paying the same fee cannot both overpay it.
    fee = db.scalar(select(StudentFee).where(StudentFee.id == data.student_fee_id).with_for_update())
    if fee is None:
        raise NotFoundError("Student fee not found")
    if fee.status not in OPEN_STATUSES:
        raise ConflictError(f"This fee is already '{fee.status}'")

    balance = fee.net_amount - _paid(db, fee.id)
    if data.amount > balance:
        raise AppError("Payment exceeds the outstanding balance", details={"balance": str(balance)})

    payment = FeePayment(
        student_fee_id=fee.id, amount=data.amount, payment_method=data.payment_method,
        payment_date=data.payment_date or datetime.now(UTC),
        receipt_number=f"RCP-{date.today():%Y%m%d}-{secrets.token_hex(4).upper()}",
        reference_number=data.reference_number, remarks=data.remarks, received_by=actor.id,
    )
    db.add(payment)
    remaining = balance - data.amount
    fee.status = "paid" if remaining == 0 else "partial"
    db.flush()
    audit.record(db, actor, "record_payment", "fee_payments", payment.id,
                 {"student_fee_id": fee.id, "amount": data.amount, "method": data.payment_method,
                  "receipt_number": payment.receipt_number})
    db.commit()
    return FeePaymentReceipt(**FeePaymentRead.model_validate(payment).model_dump(),
                             fee_status=fee.status, balance_remaining=remaining)


def payment_history(
    db: Session, params: ListParams, *, student_id: uuid.UUID | None, date_from: date | None,
    date_to: date | None, payment_method: str | None,
) -> Page[PaymentHistoryRow]:
    stmt = (
        select(FeePayment.id, FeePayment.receipt_number, FeePayment.payment_date, FeePayment.amount,
               FeePayment.payment_method, FeePayment.reference_number, FeePayment.student_fee_id,
               StudentFee.student_id, Student.admission_number,
               (Student.first_name + " " + Student.last_name).label("student_name"),
               FeeCategory.name.label("fee_category"), StudentFee.due_date)
        .join(StudentFee, StudentFee.id == FeePayment.student_fee_id)
        .join(Student, Student.id == StudentFee.student_id)
        .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
        .join(FeeCategory, FeeCategory.id == FeeStructure.fee_category_id)
        .order_by(FeePayment.payment_date.desc())
    )
    if student_id:
        stmt = stmt.where(StudentFee.student_id == student_id)
    if date_from:
        stmt = stmt.where(func.date(FeePayment.payment_date) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(FeePayment.payment_date) <= date_to)
    if payment_method:
        stmt = stmt.where(FeePayment.payment_method == payment_method)
    if params.search:
        stmt = _payments_repo.apply_search(stmt, params.search, (
            FeePayment.receipt_number, Student.admission_number, Student.first_name, Student.last_name))
    rows, total = _payments_repo.paginate(db, stmt, params.page, params.size)
    items = [PaymentHistoryRow.model_validate(dict(r._mapping)) for r in rows]
    return Page[PaymentHistoryRow].build(items, total, params.page, params.size)


def pending_report(
    db: Session, params: ListParams, *, class_id: uuid.UUID | None, section_id: uuid.UUID | None,
    student_id: uuid.UUID | None, overdue_only: bool,
) -> PendingFeeReport:
    paid = (select(FeePayment.student_fee_id, func.sum(FeePayment.amount).label("paid"))
            .group_by(FeePayment.student_fee_id).subquery())
    paid_amount = func.coalesce(paid.c.paid, ZERO)
    balance = StudentFee.net_amount - paid_amount
    today = date.today()
    stmt = (
        select(StudentFee.id.label("student_fee_id"), StudentFee.student_id, Student.admission_number,
               (Student.first_name + " " + Student.last_name).label("student_name"),
               SchoolClass.name.label("class_name"), FeeCategory.name.label("fee_category"),
               StudentFee.due_date, StudentFee.net_amount, paid_amount.label("paid_amount"),
               balance.label("balance"), StudentFee.status,
               (StudentFee.due_date < literal(today)).label("is_overdue"),
               func.sum(balance).over().label("_outstanding"))
        .join(Student, Student.id == StudentFee.student_id)
        .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
        .join(FeeCategory, FeeCategory.id == FeeStructure.fee_category_id)
        .join(SchoolClass, SchoolClass.id == FeeStructure.class_id)
        .outerjoin(paid, paid.c.student_fee_id == StudentFee.id)
        .where(StudentFee.status.in_(OPEN_STATUSES), Student.deleted_at.is_(None))
        .order_by(StudentFee.due_date, Student.first_name)
    )
    if class_id:
        stmt = stmt.where(FeeStructure.class_id == class_id)
    if student_id:
        stmt = stmt.where(StudentFee.student_id == student_id)
    if section_id:
        stmt = stmt.where(StudentFee.student_id.in_(
            select(StudentAdmission.student_id).where(
                StudentAdmission.section_id == section_id,
                StudentAdmission.academic_session_id == FeeStructure.academic_session_id)))
    if overdue_only:
        stmt = stmt.where(StudentFee.due_date < today)
    if params.search:
        stmt = _payments_repo.apply_search(stmt, params.search,
                                           (Student.admission_number, Student.first_name, Student.last_name))

    rows, total = _payments_repo.paginate(db, stmt, params.page, params.size)
    outstanding = rows[0]._outstanding if rows else ZERO
    items = [PendingFeeRow.model_validate({k: v for k, v in r._mapping.items() if not k.startswith("_")})
             for r in rows]
    page = Page[PendingFeeRow].build(items, total, params.page, params.size)
    return PendingFeeReport(**page.model_dump(exclude={"items"}), items=items, total_outstanding=outstanding)
