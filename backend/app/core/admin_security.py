"""Admin-panel authentication: opaque server-side sessions, permission checks and CSRF protection.

Admin sessions are unrelated to application-user JWTs: a user token is never accepted here, and an
admin session token is never accepted by the application endpoints.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.admin_permissions import SUPER_ADMIN_ROLE, SYSTEM_ROLES, has_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import AdminRole, AdminSession, AdminUser

ADMIN_SESSION_COOKIE = "qpi_admin_session"
CSRF_HEADER = "x-admin-request"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LAST_SEEN_WRITE_INTERVAL = timedelta(seconds=60)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str) -> str:
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def user_agent(request: Request) -> Optional[str]:
    ua = request.headers.get("user-agent")
    return ua[:255] if ua else None


def is_super_admin(admin: AdminUser) -> bool:
    return admin.role is not None and admin.role.key == SUPER_ADMIN_ROLE


def create_session(db: Session, admin: AdminUser, request: Request) -> Tuple[str, AdminSession]:
    token = secrets.token_urlsafe(48)
    now = utcnow()
    session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_token(token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.ADMIN_SESSION_MAX_HOURS),
        ip_hash=hash_ip(client_ip(request)),
        user_agent=user_agent(request),
    )
    db.add(session)
    return token, session


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        max_age=settings.ADMIN_SESSION_MAX_HOURS * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")


def revoke_sessions(db: Session, admin_id: uuid.UUID, except_session_id: Optional[uuid.UUID] = None) -> int:
    now = utcnow()
    query = select(AdminSession).where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
    if except_session_id is not None:
        query = query.where(AdminSession.id != except_session_id)
    sessions = list(db.scalars(query))
    for s in sessions:
        s.revoked_at = now
    return len(sessions)


def session_is_live(session: AdminSession, now: Optional[datetime] = None) -> bool:
    now = now or utcnow()
    return (
        session.revoked_at is None
        and as_utc(session.expires_at) > now
        and as_utc(session.last_seen_at) + timedelta(minutes=settings.ADMIN_SESSION_IDLE_MINUTES) > now
    )


def _unauthorized(detail: str = "Admin authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _extract_token(request: Request) -> Tuple[Optional[str], bool]:
    """Returns (token, from_cookie)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None, False
    return request.cookies.get(ADMIN_SESSION_COOKIE), True


def require_csrf_header(request: Request) -> None:
    """Cookie-authenticated state changes must carry a custom header. Browsers cannot add it cross-origin
    without a CORS preflight, which only the configured origins pass."""
    if request.method in UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing admin request header")


class AdminContext:
    def __init__(self, admin: AdminUser, session: AdminSession):
        self.admin = admin
        self.session = session

    @property
    def id(self) -> uuid.UUID:
        return self.admin.id

    @property
    def permissions(self):
        return self.admin.role.permissions if self.admin.role else []

    def can(self, permission: str) -> bool:
        return has_permission(self.permissions, permission)


def get_admin_context(request: Request, db: Session = Depends(get_db)) -> AdminContext:
    token, from_cookie = _extract_token(request)
    if not token:
        raise _unauthorized()
    if from_cookie:
        require_csrf_header(request)
    session = db.scalar(
        select(AdminSession)
        .options(joinedload(AdminSession.admin).joinedload(AdminUser.role))
        .where(AdminSession.token_hash == hash_token(token))
    )
    now = utcnow()
    if session is None or not session_is_live(session, now):
        raise _unauthorized("Your admin session has expired. Please sign in again.")
    admin = session.admin
    if admin is None or not admin.is_active:
        raise _unauthorized("This admin account is disabled")
    if now - as_utc(session.last_seen_at) > LAST_SEEN_WRITE_INTERVAL:
        session.last_seen_at = now
        db.commit()
    request.state.admin_id = admin.id
    return AdminContext(admin, session)


def require_permission(*permissions: str) -> Callable[..., AdminContext]:
    """Dependency: the admin must hold every listed permission."""

    def _dependency(ctx: AdminContext = Depends(get_admin_context)) -> AdminContext:
        missing = [p for p in permissions if not ctx.can(p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to perform this action ({', '.join(missing)})",
            )
        return ctx

    return _dependency


def active_super_admin_count(db: Session, exclude_admin_id: Optional[uuid.UUID] = None) -> int:
    query = (
        select(func.count(AdminUser.id))
        .join(AdminRole, AdminRole.id == AdminUser.role_id)
        .where(AdminRole.key == SUPER_ADMIN_ROLE, AdminUser.is_active.is_(True))
    )
    if exclude_admin_id is not None:
        query = query.where(AdminUser.id != exclude_admin_id)
    return db.scalar(query) or 0


def sync_system_roles(db: Session) -> None:
    """Create/refresh the built-in roles so new permissions reach existing deployments."""
    existing = {r.key: r for r in db.scalars(select(AdminRole).where(AdminRole.key.in_(list(SYSTEM_ROLES))))}
    for key, (name, description, perms) in SYSTEM_ROLES.items():
        role = existing.get(key)
        if role is None:
            db.add(AdminRole(key=key, name=name, description=description, permissions=list(perms), is_system=True))
        elif role.permissions != list(perms) or role.name != name or role.description != description or not role.is_system:
            role.name, role.description, role.permissions, role.is_system = name, description, list(perms), True
    db.commit()
