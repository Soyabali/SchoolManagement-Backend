import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class ClassSubject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Curriculum: which subjects a class studies in a session."""

    __tablename__ = "class_subjects"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "academic_session_id"),
        CheckConstraint(
            "periods_per_week IS NULL OR periods_per_week > 0", name="periods_positive"
        ),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    is_mandatory: Mapped[bool] = mapped_column(server_default=true())
    periods_per_week: Mapped[int | None] = mapped_column(SmallInteger)


class Timetable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "timetables"
    __table_args__ = (
        UniqueConstraint("section_id", "academic_session_id", "day_of_week", "period_number"),
        # A teacher cannot be in two places at once (NULL teachers never conflict).
        UniqueConstraint("teacher_id", "academic_session_id", "day_of_week", "period_number"),
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="day_of_week_range"),
        CheckConstraint("period_number > 0", name="period_positive"),
        CheckConstraint("end_time > start_time", name="times_ordered"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger)  # ISO: 1 = Monday
    period_number: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time]
    end_time: Mapped[time]
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL")
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="SET NULL"), index=True
    )


class Exam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("academic_session_id", "name"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        choice_check(
            "exam_type",
            ("unit_test", "quarterly", "midterm", "half_yearly", "final", "annual", "other"),
        ),
    )

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(100))
    exam_type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(index=True)
    end_date: Mapped[date]
    description: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(server_default=false())

    subjects: Mapped[list["ExamSubject"]] = relationship(
        back_populates="exam", passive_deletes=True
    )


class ExamSubject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_subjects"
    __table_args__ = (
        UniqueConstraint("exam_id", "class_id", "subject_id"),
        CheckConstraint("max_marks > 0", name="max_marks_positive"),
        CheckConstraint("pass_marks >= 0 AND pass_marks <= max_marks", name="pass_marks_range"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0", name="duration_positive"
        ),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"))
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True
    )
    exam_date: Mapped[date | None] = mapped_column(index=True)
    start_time: Mapped[time | None]
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    pass_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2))

    exam: Mapped[Exam] = relationship(back_populates="subjects")


class StudentExamResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_exam_results"
    __table_args__ = (
        UniqueConstraint("exam_subject_id", "student_id"),
        CheckConstraint(
            "marks_obtained IS NULL OR marks_obtained >= 0", name="marks_non_negative"
        ),
        CheckConstraint("is_absent OR marks_obtained IS NOT NULL", name="marks_or_absent"),
    )

    # RESTRICT: an exam subject that already has marks cannot be deleted.
    exam_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_subjects.id", ondelete="RESTRICT")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_absent: Mapped[bool] = mapped_column(server_default=false())
    grade_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("grades.id", ondelete="SET NULL"), index=True
    )
    remarks: Mapped[str | None] = mapped_column(String(255))
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Grade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Grading scale: percentage band -> letter grade."""

    __tablename__ = "grades"
    __table_args__ = (
        CheckConstraint(
            "min_percentage >= 0 AND min_percentage <= max_percentage AND max_percentage <= 100",
            name="percentage_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(5), unique=True)
    min_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    grade_point: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    description: Mapped[str | None] = mapped_column(String(100))
