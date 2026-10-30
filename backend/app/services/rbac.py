import time
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission, Role, RolePermission, User

ADMIN_ROLE = "admin"
_CACHE_TTL_SECONDS = 60
# role name -> (expires_at, permission codes). Role permissions change rarely and
# every request needs them, so they are cached per process.
_cache: dict[str, tuple[float, frozenset[str]]] = {}


def invalidate_permission_cache() -> None:
    _cache.clear()


def permissions_for_roles(db: Session, role_names: Iterable[str]) -> frozenset[str]:
    names = set(role_names)
    now = time.monotonic()
    stale = [n for n in names if n not in _cache or _cache[n][0] < now]
    if stale:
        rows = db.execute(
            select(Role.name, Permission.code)
            .select_from(Role)
            .outerjoin(RolePermission, RolePermission.role_id == Role.id)
            .outerjoin(Permission, Permission.id == RolePermission.permission_id)
            .where(Role.name.in_(stale))
        ).all()
        fresh: dict[str, set[str]] = {n: set() for n in stale}
        for role_name, code in rows:
            if code:
                fresh[role_name].add(code)
        for role_name, codes in fresh.items():
            _cache[role_name] = (now + _CACHE_TTL_SECONDS, frozenset(codes))
    return frozenset().union(*(_cache[n][1] for n in names if n in _cache))


def role_names(user: User) -> list[str]:
    return [role.name for role in user.roles]


def is_admin(user: User) -> bool:
    return ADMIN_ROLE in role_names(user)


def has_permission(db: Session, user: User, code: str) -> bool:
    if is_admin(user):
        return True
    return code in permissions_for_roles(db, role_names(user))


def user_permissions(db: Session, user: User) -> list[str]:
    if is_admin(user):
        return sorted(db.scalars(select(Permission.code)).all())
    return sorted(permissions_for_roles(db, role_names(user)))
