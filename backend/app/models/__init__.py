"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from app.models.academic import (
    ClassSubject,
    Exam,
    ExamSubject,
    Grade,
    StudentExamResult,
    Timetable,
)
from app.models.attendance import (
    AttendanceNotification,
    AttendanceRecord,
    AttendanceType,
    StudentAttendance,
)
from app.models.auth import Permission, RefreshToken, Role, RolePermission, User, UserRole
from app.models.communication import Announcement, Message, Notification, ParentTeacherMessage
from app.models.fee import (
    Discount,
    FeeCategory,
    FeePayment,
    FeeStructure,
    PaymentTransaction,
    Scholarship,
    StudentFee,
)
from app.models.library import Book, BookCategory, BookIssue, BookReturn
from app.models.school import AcademicSession, Classroom, School, SchoolClass, Section, Subject
from app.models.staff import (
    Staff,
    StaffAttendance,
    Teacher,
    TeacherClassAssignment,
    TeacherSubject,
)
from app.models.student import (
    Guardian,
    Student,
    StudentAdmission,
    StudentDocument,
    StudentGuardian,
)
from app.models.system import AuditLog, SystemSetting
from app.models.transport import (
    Driver,
    StudentTransportAssignment,
    TransportRoute,
    Vehicle,
)

__all__ = [
    "AcademicSession", "Announcement", "AttendanceNotification", "AttendanceRecord",
    "AttendanceType", "AuditLog", "Book", "BookCategory", "BookIssue", "BookReturn",
    "ClassSubject", "Classroom", "Discount", "Driver", "Exam", "ExamSubject", "FeeCategory",
    "FeePayment", "FeeStructure", "Grade", "Guardian", "Message", "Notification",
    "ParentTeacherMessage", "PaymentTransaction", "Permission", "RefreshToken", "Role",
    "RolePermission", "Scholarship", "School", "SchoolClass", "Section", "Staff",
    "StaffAttendance", "Student", "StudentAdmission", "StudentAttendance", "StudentDocument",
    "StudentExamResult", "StudentFee", "StudentGuardian", "StudentTransportAssignment",
    "Subject", "SystemSetting", "Teacher", "TeacherClassAssignment", "TeacherSubject",
    "Timetable", "TransportRoute", "User", "UserRole", "Vehicle",
]
