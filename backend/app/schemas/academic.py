import uuid
from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import InputSchema, Marks, Percentage, ReadSchema, Schema, Str

ExamType = Literal["unit_test", "quarterly", "midterm", "half_yearly", "final", "annual", "other"]


class ClassSubjectIn(InputSchema):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    academic_session_id: uuid.UUID
    is_mandatory: bool = True
    periods_per_week: int | None = Field(None, ge=1, le=50)


class ClassSubjectRead(ClassSubjectIn, ReadSchema):
    pass


class TimetableIn(InputSchema):
    section_id: uuid.UUID
    academic_session_id: uuid.UUID
    day_of_week: int = Field(ge=1, le=7, description="1 = Monday ... 7 = Sunday")
    period_number: int = Field(ge=1, le=20)
    start_time: time
    end_time: time
    subject_id: uuid.UUID
    teacher_id: uuid.UUID | None = None
    classroom_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TimetableRead(TimetableIn, ReadSchema):
    pass


class ExamIn(InputSchema):
    academic_session_id: uuid.UUID
    name: Str(100) = Field(examples=["Mid-Term 2026"])
    exam_type: ExamType
    start_date: date
    end_date: date
    description: str | None = Field(None, max_length=2000)
    is_published: bool = False

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class ExamRead(ExamIn, ReadSchema):
    pass


class ExamSubjectIn(InputSchema):
    exam_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    max_marks: Decimal = Field(gt=0, le=1000, max_digits=6, decimal_places=2)
    pass_marks: Marks
    exam_date: date | None = None
    start_time: time | None = None
    duration_minutes: int | None = Field(None, ge=1, le=600)

    @model_validator(mode="after")
    def _marks(self):
        if self.pass_marks > self.max_marks:
            raise ValueError("pass_marks cannot exceed max_marks")
        return self


class ExamSubjectRead(ExamSubjectIn, ReadSchema):
    pass


class GradeIn(InputSchema):
    name: Str(5) = Field(examples=["A+"])
    min_percentage: Percentage
    max_percentage: Percentage
    grade_point: Decimal | None = Field(None, ge=0, le=10, max_digits=3, decimal_places=1)
    description: Str(100) | None = None

    @model_validator(mode="after")
    def _range(self):
        if self.min_percentage > self.max_percentage:
            raise ValueError("min_percentage cannot exceed max_percentage")
        return self


class GradeRead(GradeIn, ReadSchema):
    pass


class ExamResultRead(ReadSchema):
    exam_subject_id: uuid.UUID
    student_id: uuid.UUID
    marks_obtained: Decimal | None
    is_absent: bool
    grade_id: uuid.UUID | None
    remarks: str | None
    entered_by: uuid.UUID | None


class MarksEntry(InputSchema):
    student_id: uuid.UUID
    marks_obtained: Marks | None = None
    is_absent: bool = False
    remarks: Str(255) | None = None

    @model_validator(mode="after")
    def _marks_or_absent(self):
        if not self.is_absent and self.marks_obtained is None:
            raise ValueError("marks_obtained is required unless is_absent is true")
        return self


class MarksBulkIn(InputSchema):
    exam_subject_id: uuid.UUID
    entries: list[MarksEntry] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _unique(self):
        ids = [e.student_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("each student may appear only once")
        return self


class MarksSaved(Schema):
    exam_subject_id: uuid.UUID
    saved: int


class SubjectResult(Schema):
    exam_subject_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    subject_code: str
    max_marks: Decimal
    pass_marks: Decimal
    marks_obtained: Decimal | None
    is_absent: bool
    grade: str | None
    passed: bool


class StudentResult(Schema):
    rank: int
    student_id: uuid.UUID
    admission_number: str
    student_name: str
    subjects: list[SubjectResult]
    total_obtained: Decimal
    total_max: Decimal
    percentage: Decimal
    grade: str | None
    result: Literal["pass", "fail"]


class ExamResults(Schema):
    exam_id: uuid.UUID
    exam_name: str
    students: list[StudentResult]
