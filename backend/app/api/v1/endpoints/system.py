import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import DbSession, require_permission
from app.models import AuditLog, SystemSetting
from app.schemas.system import AuditLogRead, DashboardSummary, PublicSetting, SystemSettingIn, SystemSettingRead
from app.services import dashboard as dashboard_service
from app.services.base import CRUDService

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary, tags=["Dashboard"],
            summary="Dashboard numbers",
            description="Totals for students, teachers, staff, classes and sections; today's attendance; "
                        "fee collection and pending fees; next 5 exams.",
            dependencies=[require_permission("dashboard:read")])
def dashboard_summary(db: DbSession):
    return dashboard_service.summary(db)


@router.get("/system-settings/public", response_model=list[PublicSetting], tags=["System"],
            summary="Public settings (no login needed)")
def public_settings(db: DbSession):
    rows = db.scalars(select(SystemSetting).where(SystemSetting.is_public).order_by(SystemSetting.key)).all()
    return [PublicSetting.model_validate(r) for r in rows]


for resource in (
    Resource("/system-settings", "System", "system setting", "settings",
             CRUDService(SystemSetting, label="Setting", search_fields=("key", "description")),
             SystemSettingIn, SystemSettingRead, filters={"is_public": bool}),
    Resource("/audit-logs", "System", "audit log entry", "audit",
             CRUDService(AuditLog, label="Audit log entry", search_fields=("action", "entity_type")),
             SystemSettingIn, AuditLogRead,
             filters={"user_id": uuid.UUID, "entity_type": str, "entity_id": uuid.UUID, "action": str},
             operations=frozenset({"list", "get"}),
             description="Who changed what and when. Read-only; secrets are never recorded."),
):
    router.include_router(crud_router(resource))
