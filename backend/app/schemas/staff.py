import uuid
from datetime import date, time
from typing import Literal

from pydantic import EmailStr, Field, computed_field, model_validator

from app.schemas.common import InputSchema, Phone, ReadSchema, Schema, Str, partial
from app.schemas.student import Gender

StaffType = Literal["teaching", "non_teaching", "administrative", "support"]
StaffStatus = Literal["active", "on_leave", "resigned", "terminated"]


class StaffIn(InputSchema):
    employee_code: Str(30) = Field(examples=["EMP-001"])
    first_name: Str(100)
    last_name: Str(100)
    designation: Str(100)
    staff_type: StaffType
    joining_date: date
    department: Str(100) | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    address: str | None = Field(None, max_length=1000)
    status: StaffStatus = "active"
    user_id: uuid.UUID | None = Field(None, description="Login account, optional")


class StaffRead(StaffIn, ReadSchema):
    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class TeacherStaffIn(StaffIn):
    staff_type: StaffType = "teaching"
    designation: Str(100) = "Teacher"


class TeacherCreate(InputSchema):
    staff: TeacherStaffIn
    qualification: Str(255) | None = None
    specialization: Str(255) | None = None
    experience_years: int | None = Field(None, ge=0, le=60)
    subject_ids: list[uuid.UUID] = Field(default_factory=list, description="Subjects the teacher can teach")


class TeacherUpdate(InputSchema):
    staff: partial(StaffIn, "TeacherStaffUpdate") | None = None  # type: ignore[valid-type]
    qualification: Str(255) | None = None
    specialization: Str(255) | None = None
    experience_years: int | None = Field(None, ge=0, le=60)
    subject_ids: list[uuid.UUID] | None = Field(None, description="Replaces the full subject list")


class SubjectBrief(Schema):
    id: uuid.UUID
    name: str
    code: str


class TeacherRead(ReadSchema):
    staff: StaffRead
    qualification: str | None
    specialization: str | None
    experience_years: int | None
    subjects: list[SubjectBrief]


class TeacherClassAssignmentIn(InputSchema):
    teacher_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    academic_session_id: uuid.UUID


class TeacherClassAssignmentRead(TeacherClassAssignmentIn, ReadSchema):
    pass


class StaffAttendanceIn(InputSchema):
    staff_id: uuid.UUID
    attendance_date: date
    attendance_type_id: uuid.UUID
    check_in_time: time | None = None
    check_out_time: time | None = None
    remarks: Str(255) | None = None

    @model_validator(mode="after")
    def _times(self):
        if self.check_in_time and self.check_out_time and self.check_out_time <= self.check_in_time:
            raise ValueError("check_out_time must be after check_in_time")
        return self


class StaffAttendanceRead(StaffAttendanceIn, ReadSchema):
    marked_by: uuid.UUID | None
