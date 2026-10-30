import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import InputSchema, Money, PositiveMoney, ReadSchema, Schema, Str

Frequency = Literal["one_time", "monthly", "quarterly", "half_yearly", "annual"]
DiscountType = Literal["percentage", "fixed"]
FeeStatus = Literal["pending", "partial", "paid", "waived", "cancelled"]
PaymentMethod = Literal["cash", "card", "upi", "bank_transfer", "cheque", "online"]


class FeeCategoryIn(InputSchema):
    name: Str(100) = Field(examples=["Tuition"])
    description: str | None = Field(None, max_length=1000)


class FeeCategoryRead(FeeCategoryIn, ReadSchema):
    pass


class FeeStructureIn(InputSchema):
    academic_session_id: uuid.UUID
    class_id: uuid.UUID
    fee_category_id: uuid.UUID
    amount: Money
    frequency: Frequency
    due_day: int | None = Field(None, ge=1, le=28, description="Day of month the fee falls due")
    description: str | None = Field(None, max_length=1000)


class FeeStructureRead(FeeStructureIn, ReadSchema):
    pass


class _DiscountBase(InputSchema):
    name: Str(100)
    discount_type: DiscountType
    value: PositiveMoney = Field(description="Percent (0-100) or fixed amount")
    is_active: bool = True

    @model_validator(mode="after")
    def _percent(self):
        if self.discount_type == "percentage" and self.value > 100:
            raise ValueError("percentage value cannot exceed 100")
        return self


class DiscountIn(_DiscountBase):
    description: str | None = Field(None, max_length=1000)


class DiscountRead(DiscountIn, ReadSchema):
    pass


class ScholarshipIn(_DiscountBase):
    academic_session_id: uuid.UUID | None = None
    criteria: str | None = Field(None, max_length=2000)


class ScholarshipRead(ScholarshipIn, ReadSchema):
    pass


class StudentFeeIn(InputSchema):
    student_id: uuid.UUID
    fee_structure_id: uuid.UUID
    due_date: date
    amount: Money
    discount_amount: Money = Decimal("0")
    discount_id: uuid.UUID | None = None
    scholarship_id: uuid.UUID | None = None
    status: FeeStatus = "pending"
    remarks: Str(255) | None = None

    @model_validator(mode="after")
    def _discount(self):
        if self.discount_amount > self.amount:
            raise ValueError("discount_amount cannot exceed amount")
        return self


class StudentFeeRead(StudentFeeIn, ReadSchema):
    net_amount: Decimal


class FeeAssignIn(InputSchema):
    fee_structure_id: uuid.UUID
    due_date: date
    section_id: uuid.UUID | None = Field(None, description="Limit to one section of the class")
    student_ids: list[uuid.UUID] | None = Field(
        None, max_length=1000, description="Specific students; default is every student enrolled in the class"
    )
    discount_id: uuid.UUID | None = None
    scholarship_id: uuid.UUID | None = None


class FeeAssignResult(Schema):
    fee_structure_id: uuid.UUID
    due_date: date
    amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    created: int
    skipped_existing: int


class FeePaymentIn(InputSchema):
    student_fee_id: uuid.UUID
    amount: PositiveMoney
    payment_method: PaymentMethod
    payment_date: datetime | None = Field(None, description="Defaults to now")
    reference_number: Str(100) | None = Field(None, description="UPI/cheque/bank reference")
    remarks: Str(255) | None = None


class FeePaymentRead(ReadSchema):
    student_fee_id: uuid.UUID
    amount: Decimal
    payment_date: datetime
    payment_method: str
    receipt_number: str
    reference_number: str | None
    transaction_id: uuid.UUID | None
    received_by: uuid.UUID | None
    remarks: str | None


class FeePaymentReceipt(FeePaymentRead):
    fee_status: FeeStatus
    balance_remaining: Decimal


class PaymentHistoryRow(Schema):
    id: uuid.UUID
    receipt_number: str
    payment_date: datetime
    amount: Decimal
    payment_method: str
    reference_number: str | None
    student_fee_id: uuid.UUID
    student_id: uuid.UUID
    admission_number: str
    student_name: str
    fee_category: str
    due_date: date


class PendingFeeRow(Schema):
    student_fee_id: uuid.UUID
    student_id: uuid.UUID
    admission_number: str
    student_name: str
    class_name: str
    fee_category: str
    due_date: date
    net_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    status: FeeStatus
    is_overdue: bool


class PendingFeeReport(Schema):
    items: list[PendingFeeRow]
    total: int
    page: int
    size: int
    pages: int
    total_outstanding: Decimal


class PaymentTransactionRead(ReadSchema):
    """raw_response from the gateway is deliberately never exposed."""

    student_id: uuid.UUID
    initiated_by: uuid.UUID | None
    provider: str
    provider_reference: str
    amount: Decimal
    currency: str
    status: str
