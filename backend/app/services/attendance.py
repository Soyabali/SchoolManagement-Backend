import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models import (
    AttendanceRecord,
    AttendanceType,
    Section,
    Student,
    StudentAdmission,
    StudentAttendance,
    User,
)
from app.repositories.base import Repository
from app.schemas.attendance import (
    AttendanceEntryRead,
    AttendanceMarkIn,
    AttendanceMarkResult,
    AttendanceSummary,
    AttendanceSummaryRow,
)
from app.schemas.common import ListParams, Page
from app.services import audit
from app.services.people import current_session_id

_entries_repo = Repository(StudentAttendance)


def _percent(part: int, whole: int) -> Decimal | None:
    if not whole:
        return None
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def mark(db: Session, data: AttendanceMarkIn, actor: User) -> AttendanceMarkResult:
    if db.get(Section, data.section_id) is None:
        raise NotFoundError("Section not found")
    session_id = data.academic_session_id or current_session_id(db)

    enrolled = set(db.scalars(
        select(StudentAdmission.student_id).where(
            StudentAdmission.section_id == data.section_id,
            StudentAdmission.academic_session_id == session_id,
        )
    ).all())
    not_enrolled = [str(e.student_id) for e in data.entries if e.student_id not in enrolled]
    if not_enrolled:
        raise AppError("Some students are not enrolled in this section for the session",
                       details={"student_ids": not_enrolled})

    types = {t.code.upper(): t for t in db.scalars(select(AttendanceType)).all()}
    unknown = sorted({e.status.upper() for e in data.entries} - types.keys())
    if unknown:
        raise AppError("Unknown attendance status code(s)",
                       details={"unknown": unknown, "allowed": sorted(types)})

    # One roll call per section/date/period: re-marking updates it.
    record_id = db.scalar(
        insert(AttendanceRecord)
        .values(section_id=data.section_id, academic_session_id=session_id,
                attendance_date=data.attendance_date, period_number=data.period_number,
                marked_by=actor.id)
        .on_conflict_do_update(
            constraint="uq_attendance_records_section_id_attendance_date_period_number",
            set_={"marked_by": actor.id, "updated_at": func.now()},
        )
        .returning(AttendanceRecord.id)
    )
    rows = [
        {"attendance_record_id": record_id, "student_id": e.student_id,
         "attendance_type_id": types[e.status.upper()].id, "remarks": e.remarks}
        for e in data.entries
    ]
    stmt = insert(StudentAttendance).values(rows)
    db.execute(stmt.on_conflict_do_update(
        index_elements=["attendance_record_id", "student_id"],
        set_={"attendance_type_id": stmt.excluded.attendance_type_id,
              "remarks": stmt.excluded.remarks, "updated_at": func.now()},
    ))
    present = sum(1 for e in data.entries if types[e.status.upper()].counts_as_present)
    audit.record(db, actor, "mark_attendance", "attendance_records", record_id,
                 {"section_id": data.section_id, "date": data.attendance_date,
                  "period_number": data.period_number, "count": len(rows)})
    db.commit()
    return AttendanceMarkResult(
        attendance_record_id=record_id, section_id=data.section_id,
        attendance_date=data.attendance_date, period_number=data.period_number,
        total=len(rows), present=present, absent=len(rows) - present,
    )


def list_entries(
    db: Session, params: ListParams, *, student_id: uuid.UUID | None, section_id: uuid.UUID | None,
    attendance_date: date | None, date_from: date | None, date_to: date | None, status: str | None,
) -> Page[AttendanceEntryRead]:
    stmt = (
        select(
            StudentAttendance.id, StudentAttendance.attendance_record_id,
            AttendanceRecord.attendance_date, AttendanceRecord.period_number, AttendanceRecord.section_id,
            StudentAttendance.student_id, Student.admission_number,
            (Student.first_name + " " + Student.last_name).label("student_name"),
            AttendanceType.code.label("status"), AttendanceType.name.label("status_name"),
            AttendanceType.counts_as_present, StudentAttendance.remarks,
        )
        .join(AttendanceRecord, AttendanceRecord.id == StudentAttendance.attendance_record_id)
        .join(Student, Student.id == StudentAttendance.student_id)
        .join(AttendanceType, AttendanceType.id == StudentAttendance.attendance_type_id)
    )
    if student_id:
        stmt = stmt.where(StudentAttendance.student_id == student_id)
    if section_id:
        stmt = stmt.where(AttendanceRecord.section_id == section_id)
    if attendance_date:
        stmt = stmt.where(AttendanceRecord.attendance_date == attendance_date)
    if date_from:
        stmt = stmt.where(AttendanceRecord.attendance_date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceRecord.attendance_date <= date_to)
    if status:
        stmt = stmt.where(func.upper(AttendanceType.code) == status.upper())
    if params.search:
        stmt = _entries_repo.apply_search(stmt, params.search,
                                          (Student.first_name, Student.last_name, Student.admission_number))
    stmt = stmt.order_by(AttendanceRecord.attendance_date.desc(), Student.first_name, Student.last_name)
    rows, total = _entries_repo.paginate(db, stmt, params.page, params.size)
    items = [AttendanceEntryRead.model_validate(dict(r._mapping)) for r in rows]
    return Page[AttendanceEntryRead].build(items, total, params.page, params.size)


def summary(
    db: Session, *, section_id: uuid.UUID | None, student_id: uuid.UUID | None,
    date_from: date | None, date_to: date | None,
) -> AttendanceSummary:
    if not section_id and not student_id:
        raise AppError("Provide section_id or student_id")
    present = func.count().filter(AttendanceType.counts_as_present)
    stmt = (
        select(
            Student.id.label("student_id"), Student.admission_number,
            (Student.first_name + " " + Student.last_name).label("student_name"),
            func.count().label("total_days"), present.label("present_days"),
        )
        .select_from(StudentAttendance)
        .join(AttendanceRecord, AttendanceRecord.id == StudentAttendance.attendance_record_id)
        .join(Student, Student.id == StudentAttendance.student_id)
        .join(AttendanceType, AttendanceType.id == StudentAttendance.attendance_type_id)
        # Day-level summary: count daily roll calls only, not per-period ones.
        .where(AttendanceRecord.period_number.is_(None))
        .group_by(Student.id)
        .order_by(Student.first_name, Student.last_name)
    )
    if section_id:
        stmt = stmt.where(AttendanceRecord.section_id == section_id)
    if student_id:
        stmt = stmt.where(StudentAttendance.student_id == student_id)
    if date_from:
        stmt = stmt.where(AttendanceRecord.attendance_date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceRecord.attendance_date <= date_to)

    students, total_days, total_present = [], 0, 0
    for r in db.execute(stmt).all():
        total_days += r.total_days
        total_present += r.present_days
        students.append(AttendanceSummaryRow(
            student_id=r.student_id, admission_number=r.admission_number, student_name=r.student_name,
            total_days=r.total_days, present_days=r.present_days,
            absent_days=r.total_days - r.present_days,
            attendance_percentage=_percent(r.present_days, r.total_days) or Decimal("0"),
        ))
    return AttendanceSummary(date_from=date_from, date_to=date_to, students=students,
                             overall_percentage=_percent(total_present, total_days))
