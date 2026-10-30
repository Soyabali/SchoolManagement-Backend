import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, SmallInteger, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class AttendanceType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_types"

    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    counts_as_present: Mapped[bool] = mapped_column(server_default=false())
    description: Mapped[str | None] = mapped_column(String(255))


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One roll call for a section: daily (period_number NULL) or per period."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        # NULLS NOT DISTINCT so only one daily roll call per section per date.
        UniqueConstraint(
            "section_id",
            "attendance_date",
            "period_number",
            postgresql_nulls_not_distinct=True,
        ),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    attendance_date: Mapped[date] = mapped_column(index=True)
    period_number: Mapped[int | None] = mapped_column(SmallInteger)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    remarks: Mapped[str | None] = mapped_column(String(255))

    entries: Mapped[list["StudentAttendance"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", passive_deletes=True
    )


class StudentAttendance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_attendance"
    __table_args__ = (UniqueConstraint("attendance_record_id", "student_id"),)

    attendance_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_records.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    attendance_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_types.id", ondelete="RESTRICT"), index=True
    )
    remarks: Mapped[str | None] = mapped_column(String(255))

    record: Mapped[AttendanceRecord] = relationship(back_populates="entries")
    attendance_type: Mapped[AttendanceType] = relationship(lazy="joined")


class AttendanceNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_notifications"
    __table_args__ = (
        choice_check("channel", ("sms", "email", "push", "whatsapp")),
        choice_check("status", ("pending", "sent", "failed")),
    )

    student_attendance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_attendance.id", ondelete="CASCADE"), index=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="pending", index=True)
    sent_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
