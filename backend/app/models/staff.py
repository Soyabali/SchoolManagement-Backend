import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check
from app.models.student import GENDERS


class Staff(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every employee. Teachers and drivers extend this table."""

    __tablename__ = "staff"
    __table_args__ = (
        choice_check("gender", GENDERS),
        choice_check(
            "staff_type", ("teaching", "non_teaching", "administrative", "support")
        ),
        choice_check("status", ("active", "on_leave", "resigned", "terminated")),
        Index("ix_staff_name", "last_name", "first_name"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    employee_code: Mapped[str] = mapped_column(String(30), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(10))
    date_of_birth: Mapped[date | None]
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100), index=True)
    staff_type: Mapped[str] = mapped_column(String(20), index=True)
    joining_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), server_default="active", index=True)
    deleted_at: Mapped[datetime | None]

    teacher: Mapped["Teacher | None"] = relationship(back_populates="staff")


class Teacher(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (
        CheckConstraint(
            "experience_years IS NULL OR experience_years >= 0", name="experience_non_negative"
        ),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), unique=True
    )
    qualification: Mapped[str | None] = mapped_column(String(255))
    specialization: Mapped[str | None] = mapped_column(String(255))
    experience_years: Mapped[int | None] = mapped_column(SmallInteger)

    # Inner join (staff_id is NOT NULL) so SELECT ... FOR UPDATE works on teachers.
    staff: Mapped[Staff] = relationship(back_populates="teacher", lazy="joined", innerjoin=True)
    subjects: Mapped[list["Subject"]] = relationship(  # noqa: F821
        secondary="teacher_subjects", lazy="selectin"
    )


class TeacherSubject(TimestampMixin, Base):
    """Subjects a teacher is qualified to teach."""

    __tablename__ = "teacher_subjects"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class TeacherClassAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_class_assignments"
    # One teacher per subject per section per session.
    __table_args__ = (UniqueConstraint("section_id", "subject_id", "academic_session_id"),)

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )


class StaffAttendance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_attendance"
    __table_args__ = (
        UniqueConstraint("staff_id", "attendance_date"),
        CheckConstraint(
            "check_out_time IS NULL OR check_in_time IS NULL OR check_out_time > check_in_time",
            name="times_ordered",
        ),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
    attendance_date: Mapped[date] = mapped_column(index=True)
    attendance_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_types.id", ondelete="RESTRICT"), index=True
    )
    check_in_time: Mapped[time | None]
    check_out_time: Mapped[time | None]
    remarks: Mapped[str | None] = mapped_column(String(255))
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
