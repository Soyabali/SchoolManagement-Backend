import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "announcements"
    __table_args__ = (
        choice_check(
            "audience", ("all", "students", "parents", "teachers", "staff", "class", "section")
        ),
        CheckConstraint(
            "(audience <> 'class' OR class_id IS NOT NULL)"
            " AND (audience <> 'section' OR section_id IS NOT NULL)",
            name="audience_target",
        ),
        CheckConstraint(
            "expires_at IS NULL OR published_at IS NULL OR expires_at > published_at",
            name="dates_ordered",
        ),
    )

    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20), server_default="all")
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    is_published: Mapped[bool] = mapped_column(server_default=false())
    published_at: Mapped[datetime | None] = mapped_column(index=True)
    expires_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id_read_at", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None]
    read_at: Mapped[datetime | None]


class ParentTeacherMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Conversation thread between a guardian and a teacher about one student.

    The individual messages live in `messages` (thread_id).
    """

    __tablename__ = "parent_teacher_messages"
    __table_args__ = (choice_check("status", ("open", "closed")),)

    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    last_message_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_recipient_id_read_at", "recipient_id", "read_at"),
        CheckConstraint("sender_id IS NULL OR sender_id <> recipient_id", name="not_self"),
    )

    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parent_teacher_messages.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None]
