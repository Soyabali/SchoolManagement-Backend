import uuid

from fastapi import APIRouter, Query

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.models import ClassSubject, Exam, ExamSubject, Grade, StudentExamResult, Timetable
from app.schemas.academic import (
    ClassSubjectIn,
    ClassSubjectRead,
    ExamIn,
    ExamRead,
    ExamResultRead,
    ExamResults,
    ExamSubjectIn,
    ExamSubjectRead,
    GradeIn,
    GradeRead,
    MarksBulkIn,
    MarksSaved,
    TimetableIn,
    TimetableRead,
)
from app.services import exams as exam_service
from app.services.base import CRUDService

ACADEMICS, EXAMS = "Academics", "Examinations"
router = APIRouter()


@router.post("/exams/{exam_id}/marks", response_model=MarksSaved, tags=[EXAMS],
             summary="Enter or update marks for one exam subject",
             description="Upserts marks for many students at once. Marks are checked against `max_marks`, "
                         "students must be enrolled in the exam subject's class, and each mark's grade "
                         "is looked up from the grading scale (`/grades`).",
             dependencies=[require_permission("exams:write")])
def enter_marks(exam_id: uuid.UUID, payload: MarksBulkIn, db: DbSession, user: CurrentUser):
    return exam_service.enter_marks(db, exam_id, payload, user)


@router.get("/exams/{exam_id}/results", response_model=ExamResults, tags=[EXAMS],
            summary="Calculated results: totals, percentage, grade, pass/fail and rank",
            description="A student passes when every subject is at or above its `pass_marks` (absent = fail).",
            dependencies=[require_permission("exams:read")])
def exam_results(exam_id: uuid.UUID, db: DbSession,
                 class_id: uuid.UUID | None = Query(None), section_id: uuid.UUID | None = Query(None),
                 student_id: uuid.UUID | None = Query(None)):
    return exam_service.results(db, exam_id, class_id=class_id, section_id=section_id, student_id=student_id)


for resource in (
    Resource("/class-subjects", ACADEMICS, "class subject", "academics",
             CRUDService(ClassSubject, label="Class subject"), ClassSubjectIn, ClassSubjectRead,
             filters={"class_id": uuid.UUID, "subject_id": uuid.UUID, "academic_session_id": uuid.UUID},
             description="Assign subjects to a class for a session (the curriculum)."),
    Resource("/timetables", ACADEMICS, "timetable slot", "academics",
             CRUDService(Timetable, label="Timetable slot"), TimetableIn, TimetableRead,
             filters={"section_id": uuid.UUID, "academic_session_id": uuid.UUID, "teacher_id": uuid.UUID,
                      "day_of_week": int},
             description="A section cannot have two subjects in one period, and a teacher cannot be in two "
                         "places at once (409 on conflict)."),
    Resource("/exams", EXAMS, "exam", "exams",
             CRUDService(Exam, label="Exam", search_fields=("name",)), ExamIn, ExamRead,
             filters={"academic_session_id": uuid.UUID, "exam_type": str, "is_published": bool}),
    Resource("/exam-subjects", EXAMS, "exam subject", "exams",
             CRUDService(ExamSubject, label="Exam subject"), ExamSubjectIn, ExamSubjectRead,
             filters={"exam_id": uuid.UUID, "class_id": uuid.UUID, "subject_id": uuid.UUID},
             description="One paper of an exam for one class, with max/pass marks."),
    Resource("/exam-results", EXAMS, "exam result", "exams",
             CRUDService(StudentExamResult, label="Exam result"), MarksBulkIn, ExamResultRead,
             filters={"exam_subject_id": uuid.UUID, "student_id": uuid.UUID},
             operations=frozenset({"list", "get", "delete"}),
             description="Raw marks rows. Enter marks with POST /exams/{exam_id}/marks."),
    Resource("/grades", EXAMS, "grade band", "exams",
             CRUDService(Grade, label="Grade"), GradeIn, GradeRead,
             description="Grading scale, e.g. A+ = 90-100."),
):
    router.include_router(crud_router(resource))
