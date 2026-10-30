import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import create_model

from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.schemas.auth import (
    PermissionRead,
    RegisterIn,
    RoleName,
    RolePermissionsIn,
    RoleRead,
    UserRead,
    UserRolesIn,
    UserUpdate,
)
from app.schemas.common import ListParams, Page
from app.services import auth as auth_service
from app.services import users as user_service

router = APIRouter(tags=["Users & Roles"])
service = user_service.UserService()
can_read = [require_permission("users:read")]
can_write = [require_permission("users:write")]

UserListParams = create_model("UserListParams", __base__=ListParams,
                              role=(RoleName | None, None), is_active=(bool | None, None))


@router.get("/users", response_model=Page[UserRead], dependencies=can_read, summary="List users",
            description="`search` matches email, full_name, phone. Filters: `role`, `is_active`.")
def list_users(db: DbSession, params: Annotated[UserListParams, Query()]):
    filters = params.model_dump(include={"role", "is_active"}, exclude_none=True)
    items, total = service.list(db, params, filters)
    return Page[UserRead].build([UserRead.model_validate(u) for u in items], total, params.page, params.size)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             dependencies=can_write, summary="Create a user (same rules as /auth/register)")
def create_user(payload: RegisterIn, db: DbSession, user: CurrentUser):
    return UserRead.model_validate(auth_service.register(db, payload, user))


@router.get("/users/{user_id}", response_model=UserRead, dependencies=can_read, summary="Get a user")
def get_user(user_id: uuid.UUID, db: DbSession):
    return UserRead.model_validate(service.get(db, user_id))


@router.patch("/users/{user_id}", response_model=UserRead, dependencies=can_write,
              summary="Update a user (name, phone, active)",
              description="Setting `is_active: false` also signs the user out everywhere.")
def update_user(user_id: uuid.UUID, payload: UserUpdate, db: DbSession, user: CurrentUser):
    return UserRead.model_validate(service.update(db, user_id, payload, user))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=can_write,
               summary="Archive a user", description="Deactivates and hides the account; history is kept.")
def delete_user(user_id: uuid.UUID, db: DbSession, user: CurrentUser):
    service.delete(db, user_id, user)


@router.put("/users/{user_id}/roles", response_model=UserRead, dependencies=can_write,
            summary="Replace a user's roles", description="Only an admin can grant or remove `admin`.")
def set_user_roles(user_id: uuid.UUID, payload: UserRolesIn, db: DbSession, user: CurrentUser):
    return UserRead.model_validate(service.set_roles(db, user_id, payload.roles, user))


@router.get("/roles", response_model=list[RoleRead], dependencies=can_read, summary="List roles with permissions")
def list_roles(db: DbSession):
    return [RoleRead.model_validate(r) for r in user_service.list_roles(db)]


@router.put("/roles/{role_id}/permissions", response_model=RoleRead,
            dependencies=[require_permission("settings:write")],
            summary="Replace a role's permissions", description="The admin role always has every permission.")
def set_role_permissions(role_id: uuid.UUID, payload: RolePermissionsIn, db: DbSession, user: CurrentUser):
    return RoleRead.model_validate(user_service.set_role_permissions(db, role_id, payload.permissions, user))


@router.get("/permissions", response_model=list[PermissionRead], dependencies=can_read,
            summary="List all permission codes")
def list_permissions(db: DbSession):
    return [PermissionRead.model_validate(p) for p in user_service.list_permissions(db)]
