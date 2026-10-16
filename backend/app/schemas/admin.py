"""Request bodies for the admin API (responses are plain dicts built in the routers)."""
import re
import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.admin_permissions import PERMISSIONS
from app.models.entities import UserRole


def _strip_name(v: str) -> str:
    v = (v or "").strip()
    if len(v) < 2:
        raise ValueError("Name must be at least 2 characters.")
    return v


def _check_password(v: str, min_length: int) -> str:
    if len(v) < min_length:
        raise ValueError(f"Password must be at least {min_length} characters.")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain at least one letter and one digit.")
    return v


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(max_length=72)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v, 12)


# ---------------------------------------------------------------- application users
class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(max_length=255)
    password: str = Field(max_length=72)
    role: UserRole = UserRole.FACULTY
    department_id: Optional[uuid.UUID] = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _strip_name(v)

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v, 8)


class UserUpdateIn(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[UserRole] = None
    department_id: Optional[uuid.UUID] = None
    clear_department: bool = False

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _strip_name(v)


class StatusChangeIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class PasswordResetIn(BaseModel):
    new_password: str = Field(max_length=72)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v, 8)


class BulkUserActionIn(BaseModel):
    ids: List[uuid.UUID] = Field(min_length=1, max_length=100)
    action: Literal["activate", "deactivate", "revoke_sessions"]
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------- papers
class BulkPaperActionIn(BaseModel):
    ids: List[uuid.UUID] = Field(min_length=1, max_length=100)
    action: Literal["reanalyze", "delete"]


class MarkFailedIn(BaseModel):
    reason: str = Field(default="Marked as failed by an administrator.", min_length=3, max_length=500)


# ---------------------------------------------------------------- catalog
class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(max_length=255)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{1,19}", v):
            raise ValueError("Code must be 2-20 letters, digits or hyphens.")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _strip_name(v)


class DepartmentUpdateIn(BaseModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=20)
    name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def _code(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else DepartmentIn._code(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _strip_name(v)


class CourseIn(BaseModel):
    department_id: uuid.UUID
    code: str = Field(max_length=31)
    title: str = Field(max_length=255)
    academic_year: str = Field(max_length=20)


class CourseUpdateIn(BaseModel):
    department_id: Optional[uuid.UUID] = None
    code: Optional[str] = Field(default=None, max_length=31)
    title: Optional[str] = Field(default=None, max_length=255)
    academic_year: Optional[str] = Field(default=None, max_length=20)


# ---------------------------------------------------------------- admins & roles
class AdminCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(max_length=255)
    password: str = Field(max_length=72)
    role_id: uuid.UUID

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _strip_name(v)

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v, 12)


class AdminUpdateIn(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _strip_name(v)


class AdminPasswordResetIn(BaseModel):
    new_password: str = Field(max_length=72)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v, 12)


def _check_permissions(perms: List[str]) -> List[str]:
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
    return sorted(set(perms))


class RoleIn(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=500)
    permissions: List[str] = Field(default_factory=list, max_length=len(PERMISSIONS))

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _strip_name(v)
    @field_validator("permissions")
    @classmethod
    def _perms(cls, v: List[str]) -> List[str]:
        return _check_permissions(v)


class RoleUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: Optional[List[str]] = Field(default=None, max_length=len(PERMISSIONS))

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _strip_name(v)

    @field_validator("permissions")
    @classmethod
    def _perms(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        return None if v is None else _check_permissions(v)


# ---------------------------------------------------------------- settings
class SettingsUpdateIn(BaseModel):
    values: Dict[str, Any] = Field(min_length=1)
