import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check

DISCOUNT_TYPES = ("percentage", "fixed")


class FeeCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fee_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class FeeStructure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint("academic_session_id", "class_id", "fee_category_id", "frequency"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("due_day IS NULL OR due_day BETWEEN 1 AND 28", name="due_day_range"),
        choice_check(
            "frequency", ("one_time", "monthly", "quarterly", "half_yearly", "annual")
        ),
    )

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT")
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), index=True
    )
    fee_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fee_categories.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal]
    frequency: Mapped[str] = mapped_column(String(20))
    due_day: Mapped[int | None] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text)


class Discount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discounts"
    __table_args__ = (
        choice_check("discount_type", DISCOUNT_TYPES),
        CheckConstraint(
            "value > 0 AND (discount_type <> 'percentage' OR value <= 100)", name="value_range"
        ),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True)
    discount_type: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal]
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=true())


class Scholarship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scholarships"
    __table_args__ = (
        choice_check("discount_type", DISCOUNT_TYPES),
        CheckConstraint(
            "value > 0 AND (discount_type <> 'percentage' OR value <= 100)", name="value_range"
        ),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True)
    academic_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    discount_type: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal]
    criteria: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=true())


class StudentFee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A fee charged to a student for one due date."""

    __tablename__ = "student_fees"
    __table_args__ = (
        UniqueConstraint("student_id", "fee_structure_id", "due_date"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint(
            "discount_amount >= 0 AND discount_amount <= amount", name="discount_range"
        ),
        choice_check("status", ("pending", "partial", "paid", "waived", "cancelled")),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="RESTRICT"), index=True
    )
    due_date: Mapped[date] = mapped_column(index=True)
    amount: Mapped[Decimal]
    discount_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discounts.id", ondelete="SET NULL")
    )
    scholarship_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL")
    )
    discount_amount: Mapped[Decimal] = mapped_column(server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), Computed("amount - discount_amount", persisted=True)
    )
    status: Mapped[str] = mapped_column(String(20), server_default="pending", index=True)
    remarks: Mapped[str | None] = mapped_column(String(255))

    payments: Mapped[list["FeePayment"]] = relationship(back_populates="student_fee")


class PaymentTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Online payment gateway transaction."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        choice_check("status", ("initiated", "pending", "success", "failed", "refunded")),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(50))
    provider_reference: Mapped[str] = mapped_column(String(150), unique=True)
    amount: Mapped[Decimal]
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    status: Mapped[str] = mapped_column(String(20), server_default="initiated", index=True)
    # Raw gateway payload, kept for reconciliation; never returned by the API.
    raw_response: Mapped[dict[str, Any] | None]


class FeePayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fee_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        choice_check(
            "payment_method", ("cash", "card", "upi", "bank_transfer", "cheque", "online")
        ),
    )

    student_fee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_fees.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal]
    payment_date: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    payment_method: Mapped[str] = mapped_column(String(20))
    receipt_number: Mapped[str] = mapped_column(String(30), unique=True)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="SET NULL"), index=True
    )
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    remarks: Mapped[str | None] = mapped_column(String(255))

    student_fee: Mapped[StudentFee] = relationship(back_populates="payments")
