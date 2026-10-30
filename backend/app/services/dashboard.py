from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AttendanceRecord,
    AttendanceType,
    Exam,
    FeePayment,
    SchoolClass,
    Section,
    Staff,
    Student,
    StudentAttendance,
    StudentFee,
    Teacher,
)
from app.schemas.system import DashboardSummary, FeeOverview, TodayAttendance, UpcomingExam

OPEN = ("pending", "partial")


def _scalar(stmt):
    return stmt.scalar_subquery()


def summary(db: Session) -> DashboardSummary:
    today = date.today()
    month_start = today.replace(day=1)
    money = lambda expr: func.coalesce(expr, Decimal("0.00"))  # noqa: E731

    todays_entries = (
        select(StudentAttendance.id)
        .join(AttendanceRecord, AttendanceRecord.id == StudentAttendance.attendance_record_id)
        .join(AttendanceType, AttendanceType.id == StudentAttendance.attendance_type_id)
        .where(AttendanceRecord.attendance_date == today, AttendanceRecord.period_number.is_(None))
    )
    open_fees = select(StudentFee.id).where(StudentFee.status.in_(OPEN)).subquery()

    # Every figure in one statement: one network round trip to the database.
    row = db.execute(select(
        _scalar(select(func.count()).select_from(Student)
               .where(Student.deleted_at.is_(None), Student.status == "active")).label("students"),
        _scalar(select(func.count()).select_from(Teacher).join(Staff, Staff.id == Teacher.staff_id)
               .where(Staff.deleted_at.is_(None), Staff.status == "active")).label("teachers"),
        _scalar(select(func.count()).select_from(Staff)
               .where(Staff.deleted_at.is_(None), Staff.status == "active")).label("staff"),
        _scalar(select(func.count()).select_from(SchoolClass)).label("classes"),
        _scalar(select(func.count()).select_from(Section)).label("sections"),
        _scalar(select(func.count()).select_from(todays_entries.subquery())).label("marked"),
        _scalar(select(func.count()).select_from(
            todays_entries.where(AttendanceType.counts_as_present).subquery())).label("present"),
        _scalar(select(money(func.sum(FeePayment.amount)))).label("collected"),
        _scalar(select(money(func.sum(FeePayment.amount)))
               .where(func.date(FeePayment.payment_date) >= month_start)).label("collected_month"),
        _scalar(select(func.count()).select_from(StudentFee).where(StudentFee.status.in_(OPEN))).label("pending_count"),
        _scalar(select(money(func.sum(StudentFee.net_amount))).where(StudentFee.status.in_(OPEN))).label("pending_net"),
        _scalar(select(money(func.sum(FeePayment.amount)))
               .where(FeePayment.student_fee_id.in_(select(open_fees.c.id)))).label("pending_paid"),
        _scalar(select(func.count()).select_from(StudentFee)
               .where(StudentFee.status.in_(OPEN), StudentFee.due_date < today)).label("overdue"),
    )).one()

    exams = db.scalars(select(Exam).where(Exam.end_date >= today).order_by(Exam.start_date).limit(5)).all()

    percentage = None
    if row.marked:
        percentage = (Decimal(row.present) * 100 / row.marked).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return DashboardSummary(
        total_students=row.students, total_teachers=row.teachers, total_staff=row.staff,
        total_classes=row.classes, total_sections=row.sections,
        today_attendance=TodayAttendance(date=today, students_marked=row.marked, present=row.present,
                                         absent=row.marked - row.present, attendance_percentage=percentage),
        fees=FeeOverview(total_collected=row.collected, collected_this_month=row.collected_month,
                         pending_count=row.pending_count, pending_amount=row.pending_net - row.pending_paid,
                         overdue_count=row.overdue),
        upcoming_exams=[UpcomingExam.model_validate(e) for e in exams],
    )
