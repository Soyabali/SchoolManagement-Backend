"""seed roles and attendance types

Revision ID: f1fca16a076e
Revises: 693347728e11
Create Date: 2026-10-31 00:58:28.369630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1fca16a076e'
down_revision: Union[str, Sequence[str], None] = '693347728e11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLES = [
    ("admin", "Full system administrator"),
    ("principal", "School head: academic and administrative oversight"),
    ("teacher", "Teaching staff: attendance, marks, class communication"),
    ("accountant", "Fee structures, collections and financial reports"),
    ("student", "Student portal access"),
    ("parent", "Guardian portal access"),
]

ATTENDANCE_TYPES = [
    ("P", "Present", True),
    ("A", "Absent", False),
    ("L", "Late", True),
    ("HD", "Half Day", True),
    ("LV", "On Leave", False),
]

roles = sa.table(
    "roles",
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("is_system", sa.Boolean),
)
attendance_types = sa.table(
    "attendance_types",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("counts_as_present", sa.Boolean),
)


def upgrade() -> None:
    op.bulk_insert(
        roles, [{"name": n, "description": d, "is_system": True} for n, d in ROLES]
    )
    op.bulk_insert(
        attendance_types,
        [{"code": c, "name": n, "counts_as_present": p} for c, n, p in ATTENDANCE_TYPES],
    )


def downgrade() -> None:
    op.execute(
        attendance_types.delete().where(
            attendance_types.c.code.in_([c for c, _, _ in ATTENDANCE_TYPES])
        )
    )
    op.execute(roles.delete().where(roles.c.name.in_([n for n, _ in ROLES])))
