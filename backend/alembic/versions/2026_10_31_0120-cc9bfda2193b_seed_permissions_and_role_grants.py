"""seed permissions and role grants

Revision ID: cc9bfda2193b
Revises: f1fca16a076e
Create Date: 2026-10-31 01:20:02.116488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc9bfda2193b'
down_revision: Union[str, Sequence[str], None] = 'f1fca16a076e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen copy of the permission model at this revision (migrations must not import app code).
MODULES = {
    "users": "User accounts and role assignment",
    "school": "School profile, sessions, classes, sections, subjects, classrooms",
    "students": "Students, admissions, guardians, documents",
    "staff": "Teachers, staff, class assignments",
    "academics": "Curriculum (class subjects) and timetables",
    "exams": "Exams, exam subjects, marks, grades, results",
    "attendance": "Student and staff attendance",
    "fees": "Fee setup, assignment, payments and reports",
    "library": "Books, issues and returns",
    "transport": "Vehicles, drivers, routes, assignments",
    "communication": "Announcements, notifications, messages",
    "settings": "System settings and role permissions",
    "audit": "Audit log",
    "dashboard": "Dashboard figures",
}
READ_ONLY = {"audit", "dashboard"}


def _codes() -> list[tuple[str, str, str]]:
    codes = []
    for module, description in MODULES.items():
        codes.append((f"{module}:read", module, f"View {description.lower()}"))
        if module not in READ_ONLY:
            codes.append((f"{module}:write", module, f"Create, edit and delete {description.lower()}"))
    return codes


ALL_READ = [f"{m}:read" for m in MODULES]
GRANTS = {
    "admin": [code for code, _, _ in _codes()],
    "principal": ALL_READ + [f"{m}:write" for m in (
        "school", "students", "staff", "academics", "exams", "attendance", "library", "transport", "communication")],
    "teacher": [f"{m}:read" for m in (
        "school", "students", "staff", "academics", "exams", "attendance", "library", "transport", "communication")]
    + ["exams:write", "attendance:write", "communication:write"],
    "accountant": ["school:read", "students:read", "fees:read", "fees:write", "dashboard:read", "communication:read"],
    "student": ["communication:read"],
    "parent": ["communication:read"],
}

permissions = sa.table(
    "permissions",
    sa.column("code", sa.String),
    sa.column("module", sa.String),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(permissions, [{"code": c, "module": m, "description": d} for c, m, d in _codes()])
    for role, codes in GRANTS.items():
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(:codes) "
                "WHERE r.name = :role"
            ).bindparams(sa.bindparam("codes", value=codes, type_=sa.ARRAY(sa.String)), role=role)
        )


def downgrade() -> None:
    codes = [c for c, _, _ in _codes()]
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = ANY(:codes))"
        ).bindparams(sa.bindparam("codes", value=codes, type_=sa.ARRAY(sa.String)))
    )
    op.execute(permissions.delete().where(permissions.c.code.in_(codes)))
