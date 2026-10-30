import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class School(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Profile of the (single) school this deployment serves."""

    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), server_default="Asia/Kolkata")
    established_year: Mapped[int | None] = mapped_column(SmallInteger)


class AcademicSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_sessions"
    __table_args__ = (
        CheckConstraint("end_date > start_date", name="dates_ordered"),
        # At most one current session.
        Index(
            "uq_academic_sessions_is_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    name: Mapped[str] = mapped_column(String(20), unique=True)
    start_date: Mapped[date]
    end_date: Mapped[date]
    is_current: Mapped[bool] = mapped_column(server_default=false())


class SchoolClass(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(50), unique=True)
    numeric_level: Mapped[int | None] = mapped_column(SmallInteger, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    sections: Mapped[list["Section"]] = relationship(
        back_populates="school_class", passive_deletes=True, order_by="Section.name"
    )


class Section(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("class_id", "name"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity_positive"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(10))
    capacity: Mapped[int | None] = mapped_column(SmallInteger)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), index=True
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="SET NULL"), index=True
    )

    school_class: Mapped[SchoolClass] = relationship(back_populates="sections")


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (choice_check("subject_type", ("theory", "practical", "both")),)

    name: Mapped[str] = mapped_column(String(100), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    subject_type: Mapped[str] = mapped_column(String(20), server_default="theory")
    description: Mapped[str | None] = mapped_column(Text)


class Classroom(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity_positive"),
    )

    room_number: Mapped[str] = mapped_column(String(20), unique=True)
    building: Mapped[str | None] = mapped_column(String(100))
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    capacity: Mapped[int | None] = mapped_column(SmallInteger)
