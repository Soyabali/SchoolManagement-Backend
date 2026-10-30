import uuid

from fastapi import APIRouter, status

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.models import Guardian, StudentAdmission, StudentDocument
from app.schemas.student import (
    GuardianIn,
    GuardianRead,
    StudentAdmissionIn,
    StudentAdmissionRead,
    StudentCreate,
    StudentDocumentIn,
    StudentDocumentRead,
    StudentGuardianIn,
    StudentGuardianRead,
    StudentRead,
    StudentUpdate,
)
from app.services.base import CRUDService
from app.services.people import StudentService

TAG = "Students"
router = APIRouter()
student_service = StudentService()

router.include_router(crud_router(Resource(
    "/students", TAG, "student", "students", student_service, StudentCreate, StudentRead,
    update_schema=StudentUpdate,
    filters={"status": str, "gender": str, "section_id": uuid.UUID, "class_id": uuid.UUID,
             "academic_session_id": uuid.UUID},
    description="Deleting a student archives the record (fees, marks and attendance are kept).",
)))


@router.get("/students/{student_id}/guardians", response_model=list[StudentGuardianRead], tags=[TAG],
            summary="List a student's guardians", dependencies=[require_permission("students:read")])
def list_student_guardians(student_id: uuid.UUID, db: DbSession):
    return [StudentGuardianRead.model_validate(link) for link in student_service.guardians(db, student_id)]


@router.put("/students/{student_id}/guardians/{guardian_id}", response_model=StudentGuardianRead, tags=[TAG],
            summary="Link a guardian to a student (or update the link)",
            dependencies=[require_permission("students:write")])
def link_guardian(student_id: uuid.UUID, guardian_id: uuid.UUID, payload: StudentGuardianIn,
                  db: DbSession, user: CurrentUser):
    link = student_service.link_guardian(db, student_id, guardian_id, payload, user)
    return StudentGuardianRead.model_validate(link)


@router.delete("/students/{student_id}/guardians/{guardian_id}", status_code=status.HTTP_204_NO_CONTENT,
               tags=[TAG], summary="Unlink a guardian from a student",
               dependencies=[require_permission("students:write")])
def unlink_guardian(student_id: uuid.UUID, guardian_id: uuid.UUID, db: DbSession, user: CurrentUser):
    student_service.unlink_guardian(db, student_id, guardian_id, user)


for resource in (
    Resource("/student-admissions", TAG, "admission (enrolment)", "students",
             CRUDService(StudentAdmission, label="Admission"), StudentAdmissionIn, StudentAdmissionRead,
             filters={"student_id": uuid.UUID, "section_id": uuid.UUID,
                      "academic_session_id": uuid.UUID, "status": str},
             description="A student's place in a section for one academic session."),
    Resource("/guardians", TAG, "guardian", "students",
             CRUDService(Guardian, label="Guardian", search_fields=("first_name", "last_name", "phone", "email")),
             GuardianIn, GuardianRead),
    Resource("/student-documents", TAG, "student document", "students",
             CRUDService(StudentDocument, label="Document", actor_field="uploaded_by"),
             StudentDocumentIn, StudentDocumentRead,
             filters={"student_id": uuid.UUID, "document_type": str},
             description="Metadata only: upload the file to storage first and send its URL."),
):
    router.include_router(crud_router(resource))
