import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check

GENDERS = ("male", "female", "other")


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        choice_check("gender", GENDERS),
        choice_check(
            "status", ("active", "graduated", "transferred", "withdrawn", "suspended")
        ),
        Index("ix_students_name", "last_name", "first_name"),
    )

    # Optional login account (for the student portal / mobile app).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    admission_number: Mapped[str] = mapped_column(String(30), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date]
    gender: Mapped[str] = mapped_column(String(10))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), server_default="active", index=True)
    deleted_at: Mapped[datetime | None]

    admissions: Mapped[list["StudentAdmission"]] = relationship(back_populates="student")
    guardian_links: Mapped[list["StudentGuardian"]] = relationship(
        back_populates="student", passive_deletes=True
    )
    documents: Mapped[list["StudentDocument"]] = relationship(
        back_populates="student", passive_deletes=True
    )


class StudentAdmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student's enrolment in a section for one academic session."""

    __tablename__ = "student_admissions"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_session_id"),
        UniqueConstraint("section_id", "academic_session_id", "roll_number"),
        choice_check(
            "status", ("enrolled", "promoted", "detained", "transferred", "withdrawn")
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT")
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="RESTRICT")
    )
    roll_number: Mapped[str | None] = mapped_column(String(10))
    admission_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), server_default="enrolled")

    student: Mapped[Student] = relationship(back_populates="admissions")


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guardians"

    # Optional login account with the "parent" role.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    occupation: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)

    student_links: Mapped[list["StudentGuardian"]] = relationship(
        back_populates="guardian", passive_deletes=True
    )


class StudentGuardian(TimestampMixin, Base):
    __tablename__ = "student_guardians"
    __table_args__ = (
        choice_check(
            "relation", ("father", "mother", "guardian", "grandparent", "sibling", "other")
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    relation: Mapped[str] = mapped_column(String(20))
    is_primary: Mapped[bool] = mapped_column(server_default=false())
    can_pickup: Mapped[bool] = mapped_column(server_default=false())

    student: Mapped[Student] = relationship(back_populates="guardian_links")
    guardian: Mapped[Guardian] = relationship(back_populates="student_links")


class StudentDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_documents"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    student: Mapped[Student] = relationship(back_populates="documents")
