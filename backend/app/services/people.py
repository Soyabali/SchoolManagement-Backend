import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models import (
    AcademicSession,
    Book,
    Guardian,
    Section,
    Staff,
    Student,
    StudentAdmission,
    StudentGuardian,
    Subject,
    Teacher,
    TeacherSubject,
    User,
)
from app.schemas.staff import TeacherCreate, TeacherUpdate
from app.schemas.student import StudentCreate, StudentGuardianIn
from app.services import audit
from app.services.base import CRUDService


class StudentService(CRUDService[Student]):
    def __init__(self) -> None:
        super().__init__(
            Student, label="Student",
            search_fields=("first_name", "last_name", "admission_number", "phone", "email"),
        )

    def apply_filters(self, stmt, filters):
        # section/class/session filters go through the enrolment (admission) table.
        enrolment = {k: filters.pop(k) for k in ("section_id", "class_id", "academic_session_id") if k in filters}
        stmt = super().apply_filters(stmt, filters)
        if enrolment:
            sub = select(StudentAdmission.student_id)
            if "section_id" in enrolment:
                sub = sub.where(StudentAdmission.section_id == enrolment["section_id"])
            if "academic_session_id" in enrolment:
                sub = sub.where(StudentAdmission.academic_session_id == enrolment["academic_session_id"])
            if "class_id" in enrolment:
                sub = sub.join(Section, Section.id == StudentAdmission.section_id).where(
                    Section.class_id == enrolment["class_id"]
                )
            stmt = stmt.where(Student.id.in_(sub))
        return stmt

    def create(self, db: Session, data: StudentCreate, actor: User) -> Student:
        values = data.model_dump(exclude={"admission"})
        student = self.repo.create(db, values)
        if data.admission:
            db.add(StudentAdmission(student_id=student.id, **data.admission.model_dump()))
            values["admission"] = data.admission.model_dump()
        audit.record(db, actor, "create", "students", student.id, values)
        db.commit()
        return student

    # --- guardians -----------------------------------------------------
    def guardians(self, db: Session, student_id: uuid.UUID) -> list[StudentGuardian]:
        self.get(db, student_id)
        return list(db.scalars(
            select(StudentGuardian).where(StudentGuardian.student_id == student_id)
            .join(StudentGuardian.guardian).order_by(StudentGuardian.is_primary.desc(), Guardian.first_name)
        ).all())

    def link_guardian(self, db: Session, student_id: uuid.UUID, guardian_id: uuid.UUID,
                      data: StudentGuardianIn, actor: User) -> StudentGuardian:
        self.get(db, student_id)
        if db.get(Guardian, guardian_id) is None:
            raise NotFoundError("Guardian not found")
        link = db.get(StudentGuardian, (student_id, guardian_id))
        if link is None:
            link = StudentGuardian(student_id=student_id, guardian_id=guardian_id)
            db.add(link)
        for key, value in data.model_dump().items():
            setattr(link, key, value)
        if data.is_primary:  # only one primary guardian per student
            db.execute(update(StudentGuardian)
                       .where(StudentGuardian.student_id == student_id,
                              StudentGuardian.guardian_id != guardian_id)
                       .values(is_primary=False))
        audit.record(db, actor, "link_guardian", "students", student_id,
                     {"guardian_id": guardian_id, **data.model_dump()})
        db.commit()
        db.refresh(link)
        return link

    def unlink_guardian(self, db: Session, student_id: uuid.UUID, guardian_id: uuid.UUID, actor: User) -> None:
        link = db.get(StudentGuardian, (student_id, guardian_id))
        if link is None:
            raise NotFoundError("Guardian is not linked to this student")
        db.delete(link)
        audit.record(db, actor, "unlink_guardian", "students", student_id, {"guardian_id": guardian_id})
        db.commit()


class TeacherService(CRUDService[Teacher]):
    def __init__(self) -> None:
        super().__init__(
            Teacher, label="Teacher",
            search_fields=(Staff.first_name, Staff.last_name, Staff.employee_code, Staff.email),
        )

    def list_query(self):
        return select(Teacher).join(Teacher.staff).where(Staff.deleted_at.is_(None))

    def apply_filters(self, stmt, filters):
        if department := filters.pop("department", None):
            stmt = stmt.where(Staff.department == department)
        if status := filters.pop("status", None):
            stmt = stmt.where(Staff.status == status)
        if subject_id := filters.pop("subject_id", None):
            stmt = stmt.where(Teacher.id.in_(
                select(TeacherSubject.teacher_id).where(TeacherSubject.subject_id == subject_id)))
        return super().apply_filters(stmt, filters)

    def get(self, db: Session, id: uuid.UUID, *, for_update: bool = False) -> Teacher:
        teacher = db.get(Teacher, id, with_for_update=for_update)
        if teacher is None or teacher.staff.deleted_at is not None:
            raise NotFoundError("Teacher not found")
        return teacher

    @staticmethod
    def _subjects(db: Session, ids: list[uuid.UUID]) -> list[Subject]:
        subjects = db.scalars(select(Subject).where(Subject.id.in_(set(ids)))).all()
        missing = set(ids) - {s.id for s in subjects}
        if missing:
            raise AppError("Unknown subject id(s)", details=[str(i) for i in missing])
        return list(subjects)

    def create(self, db: Session, data: TeacherCreate, actor: User) -> Teacher:
        staff = Staff(**data.staff.model_dump())
        teacher = Teacher(
            staff=staff,
            subjects=self._subjects(db, data.subject_ids) if data.subject_ids else [],
            **data.model_dump(exclude={"staff", "subject_ids"}),
        )
        db.add(teacher)
        db.flush()
        audit.record(db, actor, "create", "teachers", teacher.id, data.model_dump())
        db.commit()
        return teacher

    def update(self, db: Session, id: uuid.UUID, data: TeacherUpdate, actor: User) -> Teacher:
        teacher = self.get(db, id, for_update=True)
        values = data.model_dump(exclude_unset=True)
        for key, value in (values.pop("staff", None) or {}).items():
            setattr(teacher.staff, key, value)
        if (subject_ids := values.pop("subject_ids", None)) is not None:
            teacher.subjects = self._subjects(db, subject_ids) if subject_ids else []
        for key, value in values.items():
            setattr(teacher, key, value)
        db.flush()
        audit.record(db, actor, "update", "teachers", teacher.id, data.model_dump(exclude_unset=True))
        db.commit()
        return teacher

    def delete(self, db: Session, id: uuid.UUID, actor: User) -> None:
        # Archive the staff record: timetables, marks and messages keep pointing at it.
        teacher = self.get(db, id, for_update=True)
        teacher.staff.deleted_at = datetime.now(UTC)
        audit.record(db, actor, "archive", "teachers", teacher.id)
        db.commit()


class AcademicSessionService(CRUDService[AcademicSession]):
    def __init__(self) -> None:
        super().__init__(AcademicSession, label="Academic session", search_fields=("name",))

    @staticmethod
    def _clear_current(db: Session) -> None:
        db.execute(update(AcademicSession).where(AcademicSession.is_current).values(is_current=False))

    def before_create(self, db, values, actor):
        if values.get("is_current"):
            self._clear_current(db)
        return values

    def before_update(self, db, obj, values, actor):
        start = values.get("start_date", obj.start_date)
        end = values.get("end_date", obj.end_date)
        if end <= start:
            raise AppError("end_date must be after start_date")
        if values.get("is_current") and not obj.is_current:
            self._clear_current(db)
        return values

    def activate(self, db: Session, id: uuid.UUID, actor: User) -> AcademicSession:
        session = self.get(db, id)
        self._clear_current(db)
        session.is_current = True
        audit.record(db, actor, "activate", "academic_sessions", session.id)
        db.commit()
        db.refresh(session)
        return session


def current_session_id(db: Session) -> uuid.UUID:
    session_id = db.scalar(select(AcademicSession.id).where(AcademicSession.is_current))
    if session_id is None:
        raise AppError("No current academic session. Activate one with POST /academic-sessions/{id}/activate")
    return session_id


class BookService(CRUDService[Book]):
    def __init__(self) -> None:
        super().__init__(Book, label="Book", search_fields=("title", "author", "isbn", "publisher"))

    def before_create(self, db, values: dict[str, Any], actor):
        values["available_copies"] = values["total_copies"]
        return values

    def before_update(self, db, obj: Book, values: dict[str, Any], actor):
        if "total_copies" in values and values["total_copies"] is not None:
            on_loan = obj.total_copies - obj.available_copies
            if values["total_copies"] < on_loan:
                raise ConflictError(f"{on_loan} copies are on loan; total_copies cannot go below that")
            values["available_copies"] = values["total_copies"] - on_loan
        return values
