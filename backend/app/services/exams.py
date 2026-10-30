import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models import (
    Exam,
    ExamSubject,
    Grade,
    Section,
    Student,
    StudentAdmission,
    StudentExamResult,
    Subject,
    User,
)
from app.schemas.academic import (
    ExamResults,
    MarksBulkIn,
    MarksSaved,
    StudentResult,
    SubjectResult,
)
from app.services import audit

TWO_PLACES = Decimal("0.01")


def _pct(obtained: Decimal, maximum: Decimal) -> Decimal:
    return (obtained * 100 / maximum).quantize(TWO_PLACES, ROUND_HALF_UP) if maximum else Decimal("0")


def grade_for(percentage: Decimal, grades: list[Grade]) -> Grade | None:
    """Highest band whose range contains the percentage."""
    for grade in sorted(grades, key=lambda g: g.min_percentage, reverse=True):
        if grade.min_percentage <= percentage <= grade.max_percentage:
            return grade
    return None


def _enrolled_in_class(db: Session, class_id: uuid.UUID, session_id: uuid.UUID) -> set[uuid.UUID]:
    return set(db.scalars(
        select(StudentAdmission.student_id)
        .join(Section, Section.id == StudentAdmission.section_id)
        .where(Section.class_id == class_id, StudentAdmission.academic_session_id == session_id)
    ).all())


def enter_marks(db: Session, exam_id: uuid.UUID, data: MarksBulkIn, actor: User) -> MarksSaved:
    exam_subject = db.get(ExamSubject, data.exam_subject_id)
    if exam_subject is None or exam_subject.exam_id != exam_id:
        raise NotFoundError("Exam subject not found for this exam")
    exam = exam_subject.exam

    enrolled = _enrolled_in_class(db, exam_subject.class_id, exam.academic_session_id)
    not_enrolled = [str(e.student_id) for e in data.entries if e.student_id not in enrolled]
    if not_enrolled:
        raise AppError("Some students are not enrolled in this class for the exam's session",
                       details={"student_ids": not_enrolled})
    too_high = [str(e.student_id) for e in data.entries
                if e.marks_obtained is not None and e.marks_obtained > exam_subject.max_marks]
    if too_high:
        raise AppError(f"Marks cannot exceed max_marks ({exam_subject.max_marks})",
                       details={"student_ids": too_high})

    grades = list(db.scalars(select(Grade)).all())
    rows = []
    for e in data.entries:
        marks = None if e.is_absent else e.marks_obtained
        grade = grade_for(_pct(marks, exam_subject.max_marks), grades) if marks is not None else None
        rows.append({
            "exam_subject_id": exam_subject.id, "student_id": e.student_id, "marks_obtained": marks,
            "is_absent": e.is_absent, "grade_id": grade.id if grade else None,
            "remarks": e.remarks, "entered_by": actor.id,
        })
    stmt = insert(StudentExamResult).values(rows)
    db.execute(stmt.on_conflict_do_update(
        index_elements=["exam_subject_id", "student_id"],
        set_={k: stmt.excluded[k] for k in ("marks_obtained", "is_absent", "grade_id", "remarks", "entered_by")}
        | {"updated_at": func.now()},
    ))
    audit.record(db, actor, "enter_marks", "exam_subjects", exam_subject.id, {"count": len(rows)})
    db.commit()
    return MarksSaved(exam_subject_id=exam_subject.id, saved=len(rows))


def results(
    db: Session, exam_id: uuid.UUID, *, class_id: uuid.UUID | None,
    section_id: uuid.UUID | None, student_id: uuid.UUID | None,
) -> ExamResults:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise NotFoundError("Exam not found")

    stmt = (
        select(StudentExamResult, ExamSubject, Subject.name, Subject.code, Student.admission_number,
               (Student.first_name + " " + Student.last_name).label("student_name"),
               Grade.name.label("grade_name"))
        .join(ExamSubject, ExamSubject.id == StudentExamResult.exam_subject_id)
        .join(Subject, Subject.id == ExamSubject.subject_id)
        .join(Student, Student.id == StudentExamResult.student_id)
        .outerjoin(Grade, Grade.id == StudentExamResult.grade_id)
        .where(ExamSubject.exam_id == exam_id)
        .order_by(Subject.name)
    )
    if class_id:
        stmt = stmt.where(ExamSubject.class_id == class_id)
    if student_id:
        stmt = stmt.where(StudentExamResult.student_id == student_id)
    if section_id:
        stmt = stmt.where(StudentExamResult.student_id.in_(
            select(StudentAdmission.student_id).where(
                StudentAdmission.section_id == section_id,
                StudentAdmission.academic_session_id == exam.academic_session_id)))

    per_student: dict[uuid.UUID, dict] = defaultdict(lambda: {"subjects": []})
    for result, es, subject_name, subject_code, admission_number, student_name, grade_name in db.execute(stmt):
        entry = per_student[result.student_id]
        entry["admission_number"], entry["student_name"] = admission_number, student_name
        passed = not result.is_absent and result.marks_obtained is not None and result.marks_obtained >= es.pass_marks
        entry["subjects"].append(SubjectResult(
            exam_subject_id=es.id, subject_id=es.subject_id, subject_name=subject_name,
            subject_code=subject_code, max_marks=es.max_marks, pass_marks=es.pass_marks,
            marks_obtained=result.marks_obtained, is_absent=result.is_absent, grade=grade_name, passed=passed,
        ))

    grades = list(db.scalars(select(Grade)).all())
    students = []
    for sid, entry in per_student.items():
        total_obtained = sum((s.marks_obtained or Decimal("0") for s in entry["subjects"]), Decimal("0"))
        total_max = sum((s.max_marks for s in entry["subjects"]), Decimal("0"))
        percentage = _pct(total_obtained, total_max)
        grade = grade_for(percentage, grades)
        students.append({
            "student_id": sid, "admission_number": entry["admission_number"],
            "student_name": entry["student_name"], "subjects": entry["subjects"],
            "total_obtained": total_obtained, "total_max": total_max, "percentage": percentage,
            "grade": grade.name if grade else None,
            "result": "pass" if all(s.passed for s in entry["subjects"]) else "fail",
        })

    # Competition ranking (1, 2, 2, 4) by percentage.
    students.sort(key=lambda s: (-s["percentage"], s["student_name"]))
    ranked, previous, rank = [], None, 0
    for position, s in enumerate(students, start=1):
        if s["percentage"] != previous:
            rank, previous = position, s["percentage"]
        ranked.append(StudentResult(rank=rank, **s))
    return ExamResults(exam_id=exam.id, exam_name=exam.name, students=ranked)
