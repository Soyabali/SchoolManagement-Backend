import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.models import AttendanceNotification, AttendanceRecord, AttendanceType
from app.schemas.attendance import (
    AttendanceEntryRead,
    AttendanceMarkIn,
    AttendanceMarkResult,
    AttendanceNotificationIn,
    AttendanceNotificationRead,
    AttendanceRecordRead,
    AttendanceSummary,
    AttendanceTypeIn,
    AttendanceTypeRead,
)
from app.schemas.common import ListParams, Page
from app.services import attendance as attendance_service
from app.services.base import CRUDService

TAG = "Attendance"
router = APIRouter()


@router.post("/attendance/mark", response_model=AttendanceMarkResult, tags=[TAG],
             summary="Mark attendance for a section",
             description="Send every student's status code (P, A, L, HD, LV). Marking the same "
                         "section/date/period again updates the existing roll call.",
             dependencies=[require_permission("attendance:write")])
def mark_attendance(payload: AttendanceMarkIn, db: DbSession, user: CurrentUser):
    return attendance_service.mark(db, payload, user)


@router.get("/attendance", response_model=Page[AttendanceEntryRead], tags=[TAG],
            summary="Attendance entries by student, section and/or date",
            dependencies=[require_permission("attendance:read")])
def list_attendance(
    db: DbSession,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100, description="Student name or admission number"),
    student_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None,
    attendance_date: date | None = None, date_from: date | None = None, date_to: date | None = None,
    status: str | None = Query(None, max_length=10, description="Attendance code, e.g. A"),
):
    return attendance_service.list_entries(
        db, ListParams(page=page, size=size, search=search), student_id=student_id, section_id=section_id,
        attendance_date=attendance_date, date_from=date_from, date_to=date_to, status=status)


@router.get("/attendance/summary", response_model=AttendanceSummary, tags=[TAG],
            summary="Attendance percentage per student",
            description="Give `section_id` (whole class) or `student_id`. Counts daily roll calls only.",
            dependencies=[require_permission("attendance:read")])
def attendance_summary(db: DbSession, section_id: uuid.UUID | None = None, student_id: uuid.UUID | None = None,
                       date_from: date | None = None, date_to: date | None = None):
    return attendance_service.summary(db, section_id=section_id, student_id=student_id,
                                      date_from=date_from, date_to=date_to)


for resource in (
    Resource("/attendance-types", TAG, "attendance type", "attendance",
             CRUDService(AttendanceType, label="Attendance type", search_fields=("code", "name")),
             AttendanceTypeIn, AttendanceTypeRead, description="Status codes: P, A, L, HD, LV."),
    Resource("/attendance-records", TAG, "attendance record (roll call)", "attendance",
             CRUDService(AttendanceRecord, label="Attendance record"), AttendanceMarkIn, AttendanceRecordRead,
             filters={"section_id": uuid.UUID, "attendance_date": date, "academic_session_id": uuid.UUID},
             operations=frozenset({"list", "get", "delete"}),
             description="One row per roll call. Create them with POST /attendance/mark. "
                         "Deleting a record deletes its entries."),
    Resource("/attendance-notifications", TAG, "attendance notification", "attendance",
             CRUDService(AttendanceNotification, label="Attendance notification"),
             AttendanceNotificationIn, AttendanceNotificationRead,
             filters={"status": str, "channel": str, "guardian_id": uuid.UUID}),
):
    router.include_router(crud_router(resource))
