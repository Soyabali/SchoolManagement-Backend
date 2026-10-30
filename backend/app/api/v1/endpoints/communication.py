import uuid
from typing import Literal

from fastapi import APIRouter, Query, status

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.models import Announcement, Notification, ParentTeacherMessage
from app.schemas.common import ListParams, Page
from app.schemas.communication import (
    AnnouncementIn,
    AnnouncementRead,
    MessageIn,
    MessageRead,
    NotificationIn,
    NotificationRead,
    ParentTeacherThreadIn,
    ParentTeacherThreadRead,
)
from app.services import communication as comms
from app.services.base import CRUDService
from app.services.rbac import has_permission

TAG = "Communication"
router = APIRouter()
can_use = [require_permission("communication:read")]


@router.get("/notifications/me", response_model=Page[NotificationRead], tags=[TAG],
            summary="My notifications")
def my_notifications(user: CurrentUser, db: DbSession,
                     page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), unread_only: bool = False):
    return comms.my_notifications(db, user, ListParams(page=page, size=size), unread_only)


@router.post("/notifications/me/read-all", tags=[TAG], summary="Mark all my notifications as read")
def read_all_notifications(user: CurrentUser, db: DbSession) -> dict[str, int]:
    return {"updated": comms.mark_all_notifications_read(db, user)}


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead, tags=[TAG],
             summary="Mark one of my notifications as read")
def read_notification(notification_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return NotificationRead.model_validate(comms.mark_notification_read(db, user, notification_id))


@router.post("/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED, tags=[TAG],
             summary="Send a message to another user", dependencies=can_use)
def send_message(payload: MessageIn, user: CurrentUser, db: DbSession):
    return MessageRead.model_validate(comms.send_message(db, payload, user))


@router.get("/messages", response_model=Page[MessageRead], tags=[TAG], summary="My inbox or sent messages",
            dependencies=can_use)
def list_messages(user: CurrentUser, db: DbSession, box: Literal["inbox", "sent"] = "inbox",
                  unread_only: bool = False, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                  search: str | None = Query(None, max_length=100)):
    return comms.list_messages(db, user, ListParams(page=page, size=size, search=search),
                               box=box, unread_only=unread_only)


@router.get("/messages/{message_id}", response_model=MessageRead, tags=[TAG],
            summary="Get one of my messages", dependencies=can_use)
def get_message(message_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return MessageRead.model_validate(comms.get_message(db, user, message_id))


@router.post("/messages/{message_id}/read", response_model=MessageRead, tags=[TAG],
             summary="Mark a received message as read", dependencies=can_use)
def read_message(message_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return MessageRead.model_validate(comms.mark_message_read(db, user, message_id))


@router.get("/parent-teacher-threads/{thread_id}/messages", response_model=Page[MessageRead], tags=[TAG],
            summary="Messages in a parent-teacher thread",
            description="Visible to the thread's guardian and teacher, and to users with communication:write.",
            dependencies=can_use)
def thread_messages(thread_id: uuid.UUID, user: CurrentUser, db: DbSession,
                    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=100)):
    return comms.thread_messages(db, user, thread_id, ListParams(page=page, size=size),
                                 can_moderate=has_permission(db, user, "communication:write"))


for resource in (
    Resource("/announcements", TAG, "announcement", "communication",
             CRUDService(Announcement, label="Announcement", search_fields=("title", "body"),
                         actor_field="created_by"),
             AnnouncementIn, AnnouncementRead,
             filters={"audience": str, "is_published": bool, "class_id": uuid.UUID, "section_id": uuid.UUID}),
    Resource("/notifications", TAG, "notification (admin)", "communication",
             CRUDService(Notification, label="Notification", search_fields=("title",)),
             NotificationIn, NotificationRead,
             filters={"user_id": uuid.UUID, "notification_type": str},
             operations=frozenset({"create", "list", "delete"}),
             read_permission="communication:write",  # everyone's notifications: staff only
             description="Send notifications to users. Users read their own via GET /notifications/me."),
    Resource("/parent-teacher-threads", TAG, "parent-teacher thread", "communication",
             CRUDService(ParentTeacherMessage, label="Thread", search_fields=("subject",)),
             ParentTeacherThreadIn, ParentTeacherThreadRead,
             filters={"guardian_id": uuid.UUID, "teacher_id": uuid.UUID, "student_id": uuid.UUID, "status": str},
             read_permission="communication:write",  # all threads: staff only
             description="Staff manage threads here; participants read them via "
                         "GET /parent-teacher-threads/{id}/messages."),
):
    router.include_router(crud_router(resource))
