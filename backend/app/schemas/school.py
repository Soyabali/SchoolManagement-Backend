import uuid
from datetime import date
from typing import Literal

from pydantic import EmailStr, Field, model_validator

from app.schemas.common import InputSchema, Phone, ReadSchema, Str, Url


class SchoolIn(InputSchema):
    name: Str(200)
    code: Str(30)
    address: str | None = Field(None, max_length=1000)
    phone: Phone | None = None
    email: EmailStr | None = None
    website: Url | None = None
    logo_url: Url | None = None
    timezone: Str(50) = "Asia/Kolkata"
    established_year: int | None = Field(None, ge=1800, le=2100)


class SchoolRead(SchoolIn, ReadSchema):
    pass


class AcademicSessionIn(InputSchema):
    name: Str(20) = Field(examples=["2026-27"])
    start_date: date
    end_date: date
    is_current: bool = False

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicSessionRead(AcademicSessionIn, ReadSchema):
    pass


class ClassIn(InputSchema):
    name: Str(50) = Field(examples=["Grade 5"])
    numeric_level: int | None = Field(None, ge=0, le=20)
    description: str | None = Field(None, max_length=1000)


class ClassRead(ClassIn, ReadSchema):
    pass


class SectionIn(InputSchema):
    class_id: uuid.UUID
    name: Str(10) = Field(examples=["A"])
    capacity: int | None = Field(None, ge=1, le=500)
    class_teacher_id: uuid.UUID | None = None
    classroom_id: uuid.UUID | None = None


class SectionRead(SectionIn, ReadSchema):
    pass


class SubjectIn(InputSchema):
    name: Str(100)
    code: Str(20) = Field(examples=["MATH-05"])
    subject_type: Literal["theory", "practical", "both"] = "theory"
    description: str | None = Field(None, max_length=1000)


class SubjectRead(SubjectIn, ReadSchema):
    pass


class ClassroomIn(InputSchema):
    room_number: Str(20)
    building: Str(100) | None = None
    floor: int | None = Field(None, ge=-5, le=200)
    capacity: int | None = Field(None, ge=1, le=1000)


class ClassroomRead(ClassroomIn, ReadSchema):
    pass
