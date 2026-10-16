from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import iso, not_found, parse_id
from app.core.admin_permissions import effective_permissions
from app.core.admin_security import (
    AdminContext,
    as_utc,
    clear_session_cookie,
    create_session,
    get_admin_context,
    is_super_admin,
    require_csrf_header,
    revoke_sessions,
    session_is_live,
    set_session_cookie,
    utcnow,
)
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.entities import AdminSession, AdminUser
from app.schemas.admin import AdminLoginIn, ChangePasswordIn
from app.services.audit_service import AuditService

router = APIRouter()

_DUMMY_HASH = hash_password("admin-dummy-password-for-timing")
_BAD_CREDENTIALS = "Incorrect email or password"


def admin_profile(admin: AdminUser, session: AdminSession | None = None) -> dict:
    data = {
        "id": str(admin.id),
        "email": admin.email,
        "full_name": admin.full_name,
        "is_active": admin.is_active,
        "is_super_admin": is_super_admin(admin),
        "role": {"id": str(admin.role.id), "key": admin.role.key, "name": admin.role.name} if admin.role else None,
        "permissions": effective_permissions(admin.role.permissions if admin.role else []),
        "last_login_at": iso(admin.last_login_at),
        "created_at": iso(admin.created_at),
    }
    if session is not None:
        idle_deadline = as_utc(session.last_seen_at) + timedelta(minutes=settings.ADMIN_SESSION_IDLE_MINUTES)
        data["session"] = {
            "id": str(session.id),
            "expires_at": iso(min(as_utc(session.expires_at), idle_deadline)),
            "absolute_expires_at": iso(session.expires_at),
            "idle_timeout_minutes": settings.ADMIN_SESSION_IDLE_MINUTES,
        }
    return data


def session_payload(s: AdminSession, current_id=None) -> dict:
    return {
        "id": str(s.id),
        "created_at": iso(s.created_at),
        "last_seen_at": iso(s.last_seen_at),
        "expires_at": iso(s.expires_at),
        "revoked_at": iso(s.revoked_at),
        "user_agent": s.user_agent,
        "is_active": session_is_live(s),
        "is_current": current_id is not None and s.id == current_id,
    }


@router.post("/login")
def login(payload: AdminLoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    require_csrf_header(request)
    admin = db.scalar(
        select(AdminUser).options(joinedload(AdminUser.role)).where(func.lower(AdminUser.email) == payload.email.lower())
    )
    now = utcnow()
    if admin is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)
    if admin.locked_until is not None and as_utc(admin.locked_until) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. This account is temporarily locked; try again later.",
        )
    if not verify_password(payload.password, admin.password_hash):
        admin.failed_login_count = (admin.failed_login_count or 0) + 1
        locked = admin.failed_login_count >= settings.ADMIN_MAX_FAILED_LOGINS
        if locked:
            admin.locked_until = now + timedelta(minutes=settings.ADMIN_LOCKOUT_MINUTES)
            admin.failed_login_count = 0
        AuditService.record_admin(
            db, request, admin.id, "ADMIN_LOGIN_FAILED", "admin", admin.id, {"locked": locked}
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This admin account has been deactivated")

    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now
    token, session = create_session(db, admin, request)
    AuditService.record_admin(db, request, admin.id, "ADMIN_LOGIN", "admin", admin.id)
    db.commit()
    set_session_cookie(response, token)
    return admin_profile(admin, session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, ctx: AdminContext = Depends(get_admin_context), db: Session = Depends(get_db)):
    ctx.session.revoked_at = utcnow()
    AuditService.record_admin(db, request, ctx.id, "ADMIN_LOGOUT", "admin", ctx.id)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.get("/me")
def me(ctx: AdminContext = Depends(get_admin_context)):
    return admin_profile(ctx.admin, ctx.session)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordIn, request: Request, ctx: AdminContext = Depends(get_admin_context), db: Session = Depends(get_db)
):
    admin = ctx.admin
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=422, detail="Current password is incorrect")
    if verify_password(payload.new_password, admin.password_hash):
        raise HTTPException(status_code=422, detail="The new password must differ from the current one")
    admin.password_hash = hash_password(payload.new_password)
    admin.password_changed_at = utcnow()
    revoked = revoke_sessions(db, admin.id, except_session_id=ctx.session.id)
    AuditService.record_admin(db, request, admin.id, "ADMIN_PASSWORD_CHANGE", "admin", admin.id, {"sessions_revoked": revoked})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions")
def my_sessions(ctx: AdminContext = Depends(get_admin_context), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(AdminSession).where(AdminSession.admin_id == ctx.id).order_by(AdminSession.created_at.desc()).limit(20)
    )
    return [session_payload(s, ctx.session.id) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_my_session(
    session_id: str, request: Request, ctx: AdminContext = Depends(get_admin_context), db: Session = Depends(get_db)
):
    session = db.get(AdminSession, parse_id(session_id, "Session"))
    if session is None or session.admin_id != ctx.id:
        raise not_found("Session")
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        AuditService.record_admin(db, request, ctx.id, "ADMIN_SESSION_REVOKE", "admin_session", session.id)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
