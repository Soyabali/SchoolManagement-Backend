import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import InputSchema, ReadSchema, Str

Audience = Literal["all", "students", "parents", "teachers", "staff", "class", "section"]


class AnnouncementIn(InputSchema):
    title: Str(200)
    body: str = Field(min_length=1, max_length=10000)
    audience: Audience = "all"
    class_id: uuid.UUID | None = Field(None, description="Required when audience = class")
    section_id: uuid.UUID | None = Field(None, description="Required when audience = section")
    is_published: bool = False
    published_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _target(self):
        if self.audience == "class" and not self.class_id:
            raise ValueError("class_id is required when audience is 'class'")
        if self.audience == "section" and not self.section_id:
            raise ValueError("section_id is required when audience is 'section'")
        if self.published_at and self.expires_at and self.expires_at <= self.published_at:
            raise ValueError("expires_at must be after published_at")
        return self


class AnnouncementRead(AnnouncementIn, ReadSchema):
    created_by: uuid.UUID | None


class NotificationIn(InputSchema):
    user_id: uuid.UUID
    notification_type: Str(50) = Field(examples=["fee_reminder"])
    title: Str(200)
    body: str | None = Field(None, max_length=5000)
    data: dict[str, Any] | None = None


class NotificationRead(NotificationIn, ReadSchema):
    read_at: datetime | None


class MessageIn(InputSchema):
    recipient_id: uuid.UUID = Field(description="User id of the recipient")
    body: str = Field(min_length=1, max_length=5000)
    thread_id: uuid.UUID | None = Field(None, description="Parent-teacher thread, optional")


class MessageRead(ReadSchema):
    sender_id: uuid.UUID | None
    recipient_id: uuid.UUID
    thread_id: uuid.UUID | None
    body: str
    read_at: datetime | None


class ParentTeacherThreadIn(InputSchema):
    guardian_id: uuid.UUID
    teacher_id: uuid.UUID
    student_id: uuid.UUID
    subject: Str(200)
    status: Literal["open", "closed"] = "open"


class ParentTeacherThreadRead(ParentTeacherThreadIn, ReadSchema):
    last_message_at: datetime
