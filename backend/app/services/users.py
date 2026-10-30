import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models import Permission, Role, User
from app.schemas.auth import UserUpdate
from app.services import audit
from app.services.auth import load_roles, revoke_all
from app.services.base import CRUDService
from app.services.rbac import ADMIN_ROLE, invalidate_permission_cache, is_admin


class UserService(CRUDService[User]):
    def __init__(self) -> None:
        super().__init__(User, label="User", search_fields=("email", "full_name", "phone"))

    def apply_filters(self, stmt, filters):
        role = filters.pop("role", None)
        stmt = super().apply_filters(stmt, filters)
        if role:
            stmt = stmt.where(User.roles.any(Role.name == role))
        return stmt

    def update(self, db: Session, id: uuid.UUID, data: UserUpdate, actor: User) -> User:
        user = self.get(db, id, for_update=True)
        values = data.model_dump(exclude_unset=True)
        if values.get("is_active") is False:
            if user.id == actor.id:
                raise AppError("You cannot deactivate your own account")
            revoke_all(db, user.id)
        for key, value in values.items():
            setattr(user, key, value)
        audit.record(db, actor, "update", "users", user.id, values)
        db.commit()
        return user

    def delete(self, db: Session, id: uuid.UUID, actor: User) -> None:
        user = self.get(db, id, for_update=True)
        if user.id == actor.id:
            raise AppError("You cannot delete your own account")
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        revoke_all(db, user.id)
        audit.record(db, actor, "archive", "users", user.id)
        db.commit()

    def set_roles(self, db: Session, id: uuid.UUID, names: list[str], actor: User) -> User:
        user = self.get(db, id, for_update=True)
        current = {r.name for r in user.roles}
        if (ADMIN_ROLE in names) != (ADMIN_ROLE in current) and not is_admin(actor):
            raise PermissionDeniedError("Only an admin can grant or remove the admin role")
        if user.id == actor.id and ADMIN_ROLE in current and ADMIN_ROLE not in names:
            raise AppError("You cannot remove your own admin role")
        user.roles = load_roles(db, names)
        audit.record(db, actor, "set_roles", "users", user.id, {"roles": names})
        db.commit()
        return user


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)).all())


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)).all())


def set_role_permissions(db: Session, role_id: uuid.UUID, codes: list[str], actor: User) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFoundError("Role not found")
    if role.name == ADMIN_ROLE:
        raise AppError("The admin role always has every permission")
    permissions = db.scalars(select(Permission).where(Permission.code.in_(set(codes)))).all()
    missing = set(codes) - {p.code for p in permissions}
    if missing:
        raise AppError("Unknown permission code(s)", details=sorted(missing))
    role.permissions = list(permissions)
    audit.record(db, actor, "set_permissions", "roles", role.id, {"permissions": sorted(codes)})
    db.commit()
    invalidate_permission_cache()
    return role
