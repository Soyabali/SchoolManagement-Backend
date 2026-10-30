import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import InputSchema, ReadSchema, Schema, Str


class AttendanceTypeIn(InputSchema):
    code: Str(10) = Field(examples=["P"])
    name: Str(50)
    counts_as_present: bool = False
    description: Str(255) | None = None


class AttendanceTypeRead(AttendanceTypeIn, ReadSchema):
    pass


class AttendanceMarkEntry(InputSchema):
    student_id: uuid.UUID
    status: Str(10) = Field(description="Attendance type code: P, A, L, HD, LV", examples=["P"])
    remarks: Str(255) | None = None


class AttendanceMarkIn(InputSchema):
    section_id: uuid.UUID
    attendance_date: date = Field(default_factory=date.today)
    period_number: int | None = Field(None, ge=1, le=20, description="Omit for daily attendance")
    academic_session_id: uuid.UUID | None = Field(None, description="Defaults to the current session")
    entries: list[AttendanceMarkEntry] = Field(min_length=1, max_length=500)

    @field_validator("attendance_date")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("attendance_date cannot be in the future")
        return value

    @model_validator(mode="after")
    def _unique(self):
        ids = [e.student_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("each student may appear only once")
        return self


class AttendanceMarkResult(Schema):
    attendance_record_id: uuid.UUID
    section_id: uuid.UUID
    attendance_date: date
    period_number: int | None
    total: int
    present: int
    absent: int


class AttendanceEntryRead(Schema):
    id: uuid.UUID
    attendance_record_id: uuid.UUID
    attendance_date: date
    period_number: int | None
    section_id: uuid.UUID
    student_id: uuid.UUID
    admission_number: str
    student_name: str
    status: str
    status_name: str
    counts_as_present: bool
    remarks: str | None


class AttendanceSummaryRow(Schema):
    student_id: uuid.UUID
    admission_number: str
    student_name: str
    total_days: int
    present_days: int
    absent_days: int
    attendance_percentage: Decimal


class AttendanceSummary(Schema):
    date_from: date | None
    date_to: date | None
    students: list[AttendanceSummaryRow]
    overall_percentage: Decimal | None


class AttendanceRecordRead(ReadSchema):
    section_id: uuid.UUID
    academic_session_id: uuid.UUID
    attendance_date: date
    period_number: int | None
    marked_by: uuid.UUID | None
    remarks: str | None


class AttendanceNotificationIn(InputSchema):
    student_attendance_id: uuid.UUID
    guardian_id: uuid.UUID
    channel: Literal["sms", "email", "push", "whatsapp"]
    status: Literal["pending", "sent", "failed"] = "pending"
    sent_at: datetime | None = None
    error_message: str | None = Field(None, max_length=2000)


class AttendanceNotificationRead(AttendanceNotificationIn, ReadSchema):
    pass
