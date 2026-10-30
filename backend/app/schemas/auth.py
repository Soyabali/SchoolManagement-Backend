import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, EmailStr, Field, field_validator

from app.schemas.common import InputSchema, Phone, ReadSchema, Schema, Str

RoleName = Literal["admin", "principal", "teacher", "accountant", "student", "parent"]


def _strong_password(value: str) -> str:
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ValueError("must contain at least one letter and one digit")
    return value


Password = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(_strong_password)]
Email = Annotated[EmailStr, AfterValidator(str.lower)]


class RegisterIn(InputSchema):
    email: Email
    password: Password
    full_name: Str(150)
    phone: Phone | None = None
    roles: list[RoleName] = Field(
        default_factory=list,
        description="Ignored for the very first user (always admin). Required otherwise.",
    )


class LoginIn(InputSchema):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(InputSchema):
    refresh_token: str = Field(min_length=10, max_length=200)


class ChangePasswordIn(InputSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class TokenResponse(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class UserRead(ReadSchema):
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    is_verified: bool
    last_login_at: datetime | None
    roles: list[str]

    @field_validator("roles", mode="before")
    @classmethod
    def _role_names(cls, value: object) -> object:
        return [getattr(r, "name", r) for r in value] if isinstance(value, list) else value


class MeRead(UserRead):
    permissions: list[str]


class UserUpdate(InputSchema):
    full_name: Str(150) | None = None
    phone: Phone | None = None
    is_active: bool | None = None


class UserRolesIn(InputSchema):
    roles: list[RoleName] = Field(min_length=1)


class PermissionRead(ReadSchema):
    code: str
    module: str
    description: str | None


class RoleRead(ReadSchema):
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]

    @field_validator("permissions", mode="before")
    @classmethod
    def _codes(cls, value: object) -> object:
        return sorted(getattr(p, "code", p) for p in value) if isinstance(value, list) else value


class RolePermissionsIn(InputSchema):
    permissions: list[Str(100)] = Field(description="Full list of permission codes for the role")


class UserFilterId(Schema):
    id: uuid.UUID
