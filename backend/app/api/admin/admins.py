"""Admin accounts, roles and the permission catalog.

Guards: nobody can grant permissions they do not hold, only Super Admins create/modify Super Admins,
the last active Super Admin cannot be demoted, deactivated or deleted, and admins cannot lock
themselves out (change their own role, deactivate or delete themselves).
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.auth import session_payload
from app.api.admin.common import conflict, iso, like_pattern, not_found, parse_id
from app.core.admin_permissions import (
    SUPER_ADMIN_ROLE,
    WILDCARD,
    effective_permissions,
    has_permission,
    permission_catalog,
)
from app.core.admin_security import (
    AdminContext,
    active_super_admin_count,
    as_utc,
    is_super_admin,
    require_permission,
    revoke_sessions,
    session_is_live,
    utcnow,
)
from app.core.security import hash_password
from app.db.session import get_db
from app.models.entities import AdminRole, AdminSession, AdminUser, AuditLog
from app.schemas.admin import AdminCreateIn, AdminPasswordResetIn, AdminUpdateIn, RoleIn, RoleUpdateIn
from app.services.audit_service import AuditService

router = APIRouter()


def _forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def role_row(role: AdminRole, admin_count: int = 0) -> dict:
    return {
        "id": str(role.id),
        "key": role.key,
        "name": role.name,
        "description": role.description,
        "permissions": effective_permissions(role.permissions),
        "is_wildcard": WILDCARD in (role.permissions or []),
        "is_system": role.is_system,
        "admin_count": admin_count,
        "created_at": iso(role.created_at),
        "updated_at": iso(role.updated_at),
    }


def admin_row(a: AdminUser, active_sessions: int = 0) -> dict:
    locked = a.locked_until is not None and as_utc(a.locked_until) > utcnow()
    return {
        "id": str(a.id),
        "email": a.email,
        "full_name": a.full_name,
        "role": {"id": str(a.role.id), "key": a.role.key, "name": a.role.name} if a.role else None,
        "is_super_admin": is_super_admin(a),
        "is_active": a.is_active,
        "is_locked": locked,
        "locked_until": iso(a.locked_until) if locked else None,
        "last_login_at": iso(a.last_login_at),
        "password_changed_at": iso(a.password_changed_at),
        "active_sessions": active_sessions,
        "created_at": iso(a.created_at),
    }


def _ensure_can_grant(ctx: AdminContext, role: AdminRole) -> None:
    """Privilege-escalation guard: the actor must already hold every permission of the role."""
    if role.key == SUPER_ADMIN_ROLE or WILDCARD in (role.permissions or []):
        if not is_super_admin(ctx.admin):
            raise _forbidden("Only a Super Admin can assign the Super Admin role")
        return
    missing = [p for p in role.permissions or [] if not ctx.can(p)]
    if missing:
        raise _forbidden(f"You cannot assign a role with permissions you do not hold: {', '.join(missing)}")


def _ensure_can_modify(ctx: AdminContext, target: AdminUser) -> None:
    if is_super_admin(target) and not is_super_admin(ctx.admin):
        raise _forbidden("Only a Super Admin can modify another Super Admin")


def _active_session_counts(db: Session, ids) -> dict:
    if not ids:
        return {}
    counts = {}
    for s in db.scalars(select(AdminSession).where(AdminSession.admin_id.in_(ids), AdminSession.revoked_at.is_(None))):
        if session_is_live(s):
            counts[s.admin_id] = counts.get(s.admin_id, 0) + 1
    return counts


def _get_admin(db: Session, admin_id: str) -> AdminUser:
    admin = db.scalar(select(AdminUser).options(joinedload(AdminUser.role)).where(AdminUser.id == parse_id(admin_id, "Admin")))
    if admin is None:
        raise not_found("Admin")
    return admin


def _get_role(db: Session, role_id) -> AdminRole:
    role = db.get(AdminRole, parse_id(role_id, "Role"))
    if role is None:
        raise not_found("Role")
    return role


# ------------------------------------------------------------------ admins
@router.get("/admins")
def list_admins(
    search: Optional[str] = Query(None, max_length=100),
    _: AdminContext = Depends(require_permission("admins.view")),
    db: Session = Depends(get_db),
):
    query = select(AdminUser).options(joinedload(AdminUser.role))
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(func.lower(AdminUser.email).like(pattern, escape="\\"),
                                func.lower(AdminUser.full_name).like(pattern, escape="\\")))
    admins = db.scalars(query.order_by(AdminUser.created_at)).all()
    counts = _active_session_counts(db, [a.id for a in admins])
    return [admin_row(a, counts.get(a.id, 0)) for a in admins]


@router.post("/admins", status_code=status.HTTP_201_CREATED)
def create_admin(payload: AdminCreateIn, request: Request,
                 ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(AdminUser.id).where(func.lower(AdminUser.email) == email)):
        raise conflict("An admin with this email already exists")
    role = _get_role(db, payload.role_id)
    _ensure_can_grant(ctx, role)
    admin = AdminUser(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password),
                      role_id=role.id, created_by_id=ctx.id, password_changed_at=utcnow())
    db.add(admin)
    db.flush()
    AuditService.record_admin(db, request, ctx.id, "ADMIN_CREATE", "admin", admin.id, {"email": email, "role": role.key})
    db.commit()
    return admin_row(_get_admin(db, str(admin.id)))


@router.get("/admins/{admin_id}")
def get_admin(admin_id: str, ctx: AdminContext = Depends(require_permission("admins.view")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    sessions = db.scalars(
        select(AdminSession).where(AdminSession.admin_id == admin.id).order_by(AdminSession.created_at.desc()).limit(20)
    ).all()
    actions = db.scalars(
        select(AuditLog).where(AuditLog.admin_id == admin.id).order_by(AuditLog.created_at.desc()).limit(20)
    ).all() if ctx.can("audit.view") else []
    return {
        **admin_row(admin, sum(1 for s in sessions if session_is_live(s))),
        "permissions": effective_permissions(admin.role.permissions if admin.role else []),
        "sessions": [session_payload(s, ctx.session.id) for s in sessions],
        "recent_actions": [{"id": str(a.id), "action": a.action, "entity_type": a.entity_type,
                            "entity_id": str(a.resource_id), "created_at": iso(a.created_at)} for a in actions],
    }


@router.patch("/admins/{admin_id}")
def update_admin(admin_id: str, payload: AdminUpdateIn, request: Request,
                 ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    _ensure_can_modify(ctx, admin)
    is_self = admin.id == ctx.id
    changes = {}
    if payload.email is not None and payload.email.lower() != admin.email:
        email = payload.email.lower()
        if db.scalar(select(AdminUser.id).where(func.lower(AdminUser.email) == email, AdminUser.id != admin.id)):
            raise conflict("Another admin already uses this email")
        changes["email"] = [admin.email, email]
        admin.email = email
    if payload.full_name is not None and payload.full_name != admin.full_name:
        changes["full_name"] = [admin.full_name, payload.full_name]
        admin.full_name = payload.full_name
    if payload.role_id is not None and payload.role_id != admin.role_id:
        if is_self:
            raise _forbidden("You cannot change your own role")
        role = _get_role(db, payload.role_id)
        _ensure_can_grant(ctx, role)
        if is_super_admin(admin) and role.key != SUPER_ADMIN_ROLE and admin.is_active \
                and active_super_admin_count(db, exclude_admin_id=admin.id) == 0:
            raise conflict("This is the last active Super Admin; promote someone else first")
        changes["role"] = [admin.role.key, role.key]
        admin.role_id = role.id
        revoke_sessions(db, admin.id)  # permissions change: force a fresh sign-in
    if payload.is_active is not None and payload.is_active != admin.is_active:
        if is_self:
            raise _forbidden("You cannot deactivate your own account")
        if not payload.is_active and is_super_admin(admin) and active_super_admin_count(db, exclude_admin_id=admin.id) == 0:
            raise conflict("This is the last active Super Admin and cannot be deactivated")
        changes["is_active"] = [admin.is_active, payload.is_active]
        admin.is_active = payload.is_active
        if not payload.is_active:
            revoke_sessions(db, admin.id)
    if changes:
        AuditService.record_admin(db, request, ctx.id, "ADMIN_UPDATE", "admin", admin.id, {"changes": changes})
        db.commit()
        db.expire(admin)
    return admin_row(_get_admin(db, admin_id))


@router.post("/admins/{admin_id}/revoke-sessions")
def revoke_admin_sessions(admin_id: str, request: Request,
                          ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    _ensure_can_modify(ctx, admin)
    keep = ctx.session.id if admin.id == ctx.id else None
    revoked = revoke_sessions(db, admin.id, except_session_id=keep)
    AuditService.record_admin(db, request, ctx.id, "ADMIN_REVOKE_SESSIONS", "admin", admin.id, {"revoked": revoked})
    db.commit()
    return {"revoked": revoked}


@router.post("/admins/{admin_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_admin_password(admin_id: str, payload: AdminPasswordResetIn, request: Request,
                         ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    _ensure_can_modify(ctx, admin)
    if admin.id == ctx.id:
        raise _forbidden("Use 'Change password' on your profile to change your own password")
    admin.password_hash = hash_password(payload.new_password)
    admin.password_changed_at = utcnow()
    admin.failed_login_count = 0
    admin.locked_until = None
    revoke_sessions(db, admin.id)
    AuditService.record_admin(db, request, ctx.id, "ADMIN_PASSWORD_RESET", "admin", admin.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admins/{admin_id}/unlock")
def unlock_admin(admin_id: str, request: Request,
                 ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    _ensure_can_modify(ctx, admin)
    admin.locked_until = None
    admin.failed_login_count = 0
    AuditService.record_admin(db, request, ctx.id, "ADMIN_UNLOCK", "admin", admin.id)
    db.commit()
    return admin_row(_get_admin(db, admin_id))


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(admin_id: str, request: Request,
                 ctx: AdminContext = Depends(require_permission("admins.manage")), db: Session = Depends(get_db)):
    admin = _get_admin(db, admin_id)
    if admin.id == ctx.id:
        raise _forbidden("You cannot delete your own account")
    _ensure_can_modify(ctx, admin)
    if is_super_admin(admin) and admin.is_active and active_super_admin_count(db, exclude_admin_id=admin.id) == 0:
        raise conflict("This is the last active Super Admin and cannot be deleted")
    # Audit entries keep the admin id (SET NULL on delete) plus this snapshot.
    AuditService.record_admin(db, request, ctx.id, "ADMIN_DELETE", "admin", admin.id,
                              {"email": admin.email, "full_name": admin.full_name, "role": admin.role.key})
    db.delete(admin)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ roles & permissions
@router.get("/permissions")
def list_permissions(_: AdminContext = Depends(require_permission("admins.view"))):
    return permission_catalog()


def _role_counts(db: Session) -> dict:
    return dict(db.execute(select(AdminUser.role_id, func.count(AdminUser.id)).group_by(AdminUser.role_id)).all())


@router.get("/roles")
def list_roles(_: AdminContext = Depends(require_permission("admins.view")), db: Session = Depends(get_db)):
    counts = _role_counts(db)
    roles = db.scalars(select(AdminRole).order_by(AdminRole.is_system.desc(), AdminRole.name)).all()
    return [role_row(r, counts.get(r.id, 0)) for r in roles]


def _ensure_can_grant_permissions(ctx: AdminContext, permissions) -> None:
    missing = [p for p in permissions if not has_permission(ctx.permissions, p)]
    if missing:
        raise _forbidden(f"You cannot grant permissions you do not hold: {', '.join(missing)}")


def _role_key(name: str) -> str:
    return "custom_" + (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "role")[:40]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleIn, request: Request,
                ctx: AdminContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)):
    _ensure_can_grant_permissions(ctx, payload.permissions)
    if db.scalar(select(AdminRole.id).where(func.lower(AdminRole.name) == payload.name.lower())):
        raise conflict("A role with this name already exists")
    key = _role_key(payload.name)
    if db.scalar(select(AdminRole.id).where(AdminRole.key == key)):
        raise conflict("A role with a similar name already exists")
    role = AdminRole(key=key, name=payload.name, description=payload.description.strip(),
                     permissions=payload.permissions, is_system=False)
    db.add(role)
    db.flush()
    AuditService.record_admin(db, request, ctx.id, "ROLE_CREATE", "admin_role", role.id,
                              {"name": role.name, "permissions": role.permissions})
    db.commit()
    return role_row(role)


@router.patch("/roles/{role_id}")
def update_role(role_id: str, payload: RoleUpdateIn, request: Request,
                ctx: AdminContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)):
    role = _get_role(db, role_id)
    if role.is_system:
        raise _forbidden("Built-in roles cannot be modified; create a custom role instead")
    if ctx.admin.role_id == role.id:
        raise _forbidden("You cannot edit the role you are assigned to")
    changes = {}
    if payload.name is not None and payload.name != role.name:
        if db.scalar(select(AdminRole.id).where(func.lower(AdminRole.name) == payload.name.lower(), AdminRole.id != role.id)):
            raise conflict("A role with this name already exists")
        changes["name"] = [role.name, payload.name]
        role.name = payload.name
    if payload.description is not None and payload.description.strip() != role.description:
        changes["description"] = [role.description, payload.description.strip()]
        role.description = payload.description.strip()
    if payload.permissions is not None and sorted(payload.permissions) != sorted(role.permissions or []):
        _ensure_can_grant_permissions(ctx, payload.permissions)
        # Removing permissions is always allowed; the guard above covers adding ones the actor lacks.
        changes["permissions"] = {"added": sorted(set(payload.permissions) - set(role.permissions or [])),
                                  "removed": sorted(set(role.permissions or []) - set(payload.permissions))}
        role.permissions = payload.permissions
    if changes:
        AuditService.record_admin(db, request, ctx.id, "ROLE_UPDATE", "admin_role", role.id, {"changes": changes})
        db.commit()
    return role_row(role, _role_counts(db).get(role.id, 0))


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: str, request: Request,
                ctx: AdminContext = Depends(require_permission("roles.manage")), db: Session = Depends(get_db)):
    role = _get_role(db, role_id)
    if role.is_system:
        raise _forbidden("Built-in roles cannot be deleted")
    assigned = _role_counts(db).get(role.id, 0)
    if assigned:
        raise conflict(f"{assigned} admin(s) still have this role; reassign them first")
    AuditService.record_admin(db, request, ctx.id, "ROLE_DELETE", "admin_role", role.id, {"name": role.name})
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
