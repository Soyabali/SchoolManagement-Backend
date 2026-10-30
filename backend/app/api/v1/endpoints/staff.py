import uuid
from datetime import date

from fastapi import APIRouter

from app.api.v1.crud import Resource, crud_router
from app.models import Staff, StaffAttendance, TeacherClassAssignment
from app.schemas.staff import (
    StaffAttendanceIn,
    StaffAttendanceRead,
    StaffIn,
    StaffRead,
    TeacherClassAssignmentIn,
    TeacherClassAssignmentRead,
    TeacherCreate,
    TeacherRead,
    TeacherUpdate,
)
from app.services.base import CRUDService
from app.services.people import TeacherService

TAG = "Teachers & Staff"
router = APIRouter()

for resource in (
    Resource("/teachers", TAG, "teacher", "staff", TeacherService(), TeacherCreate, TeacherRead,
             update_schema=TeacherUpdate,
             filters={"department": str, "status": str, "subject_id": uuid.UUID},
             description="Creating a teacher also creates their staff record (send it under `staff`). "
                         "Deleting archives the staff record."),
    Resource("/staff", TAG, "staff member", "staff",
             CRUDService(Staff, label="Staff member",
                         search_fields=("first_name", "last_name", "employee_code", "email", "phone")),
             StaffIn, StaffRead,
             filters={"staff_type": str, "department": str, "status": str},
             description="All employees (teachers appear here too)."),
    Resource("/teacher-class-assignments", TAG, "teacher class assignment", "staff",
             CRUDService(TeacherClassAssignment, label="Assignment"),
             TeacherClassAssignmentIn, TeacherClassAssignmentRead,
             filters={"teacher_id": uuid.UUID, "section_id": uuid.UUID, "subject_id": uuid.UUID,
                      "academic_session_id": uuid.UUID},
             description="Which teacher teaches which subject to which section (one per subject/section/session)."),
    Resource("/staff-attendance", TAG, "staff attendance record", "attendance",
             CRUDService(StaffAttendance, label="Staff attendance", actor_field="marked_by"),
             StaffAttendanceIn, StaffAttendanceRead,
             filters={"staff_id": uuid.UUID, "attendance_date": date}),
):
    router.include_router(crud_router(resource))
