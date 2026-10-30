import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.common import InputSchema, ReadSchema, Schema


class SystemSettingIn(InputSchema):
    key: str = Field(pattern=r"^[a-z0-9_.]{2,100}$", examples=["library.fine_per_day"])
    value: dict[str, Any] = Field(examples=[{"amount": 5}])
    description: str | None = Field(None, max_length=1000)
    is_public: bool = Field(False, description="Public settings are readable without logging in")


class SystemSettingRead(SystemSettingIn, ReadSchema):
    pass


class PublicSetting(Schema):
    key: str
    value: dict[str, Any]


class AuditLogRead(Schema):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    changes: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class UpcomingExam(Schema):
    id: uuid.UUID
    name: str
    exam_type: str
    start_date: date
    end_date: date


class TodayAttendance(Schema):
    date: date
    students_marked: int
    present: int
    absent: int
    attendance_percentage: Decimal | None


class FeeOverview(Schema):
    total_collected: Decimal
    collected_this_month: Decimal
    pending_count: int
    pending_amount: Decimal
    overdue_count: int


class DashboardSummary(Schema):
    total_students: int
    total_teachers: int
    total_staff: int
    total_classes: int
    total_sections: int
    today_attendance: TodayAttendance
    fees: FeeOverview
    upcoming_exams: list[UpcomingExam]
