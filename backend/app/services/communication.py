import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models import Guardian, Message, Notification, ParentTeacherMessage, Staff, Teacher, User
from app.repositories.base import Repository
from app.schemas.common import ListParams, Page
from app.schemas.communication import MessageIn, MessageRead, NotificationRead

_messages = Repository(Message)
_notifications = Repository(Notification)


def _now() -> datetime:
    return datetime.now(UTC)


def _thread_participants(db: Session, thread: ParentTeacherMessage) -> set[uuid.UUID]:
    row = db.execute(
        select(Guardian.user_id, Staff.user_id)
        .select_from(ParentTeacherMessage)
        .join(Guardian, Guardian.id == ParentTeacherMessage.guardian_id)
        .join(Teacher, Teacher.id == ParentTeacherMessage.teacher_id)
        .join(Staff, Staff.id == Teacher.staff_id)
        .where(ParentTeacherMessage.id == thread.id)
    ).one()
    return {uid for uid in row if uid}


def send_message(db: Session, data: MessageIn, sender: User) -> Message:
    if data.recipient_id == sender.id:
        raise AppError("You cannot message yourself")
    recipient = db.get(User, data.recipient_id)
    if recipient is None or recipient.deleted_at is not None or not recipient.is_active:
        raise NotFoundError("Recipient not found")
    if data.thread_id:
        thread = db.get(ParentTeacherMessage, data.thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        if {sender.id, recipient.id} - _thread_participants(db, thread):
            raise PermissionDeniedError("Only the thread's guardian and teacher can message in it")
        if thread.status == "closed":
            raise AppError("This thread is closed")
        thread.last_message_at = _now()
    message = Message(sender_id=sender.id, **data.model_dump())
    db.add(message)
    db.commit()
    return message


def list_messages(db: Session, user: User, params: ListParams, *, box: str, unread_only: bool) -> Page[MessageRead]:
    column = Message.recipient_id if box == "inbox" else Message.sender_id
    stmt = select(Message).where(column == user.id)
    if unread_only:
        stmt = stmt.where(Message.read_at.is_(None))
    items, total = _messages.list(db, params, stmt=stmt, search_fields=("body",))
    return Page[MessageRead].build([MessageRead.model_validate(m) for m in items], total, params.page, params.size)


def thread_messages(db: Session, user: User, thread_id: uuid.UUID, params: ListParams,
                    can_moderate: bool) -> Page[MessageRead]:
    thread = db.get(ParentTeacherMessage, thread_id)
    if thread is None:
        raise NotFoundError("Thread not found")
    if not can_moderate and user.id not in _thread_participants(db, thread):
        raise NotFoundError("Thread not found")
    items, total = _messages.list(db, params, stmt=select(Message).where(Message.thread_id == thread_id))
    return Page[MessageRead].build([MessageRead.model_validate(m) for m in items], total, params.page, params.size)


def get_message(db: Session, user: User, message_id: uuid.UUID) -> Message:
    message = db.get(Message, message_id)
    # 404 rather than 403 so message ids cannot be probed.
    if message is None or user.id not in (message.sender_id, message.recipient_id):
        raise NotFoundError("Message not found")
    return message


def mark_message_read(db: Session, user: User, message_id: uuid.UUID) -> Message:
    message = get_message(db, user, message_id)
    if message.recipient_id != user.id:
        raise PermissionDeniedError("Only the recipient can mark a message as read")
    if message.read_at is None:
        message.read_at = _now()
        db.commit()
    return message


def my_notifications(db: Session, user: User, params: ListParams, unread_only: bool) -> Page[NotificationRead]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    items, total = _notifications.list(db, params, stmt=stmt, search_fields=("title", "body"))
    return Page[NotificationRead].build([NotificationRead.model_validate(n) for n in items],
                                        total, params.page, params.size)


def mark_notification_read(db: Session, user: User, notification_id: uuid.UUID) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("Notification not found")
    if notification.read_at is None:
        notification.read_at = _now()
        db.commit()
    return notification


def mark_all_notifications_read(db: Session, user: User) -> int:
    result = db.execute(update(Notification)
                        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
                        .values(read_at=_now()))
    db.commit()
    return result.rowcount
