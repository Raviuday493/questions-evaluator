"""Read-only audit log. There are deliberately no update or delete endpoints."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import (
    EXPORT_ROW_LIMIT,
    Page,
    csv_response,
    invalid,
    iso,
    like_pattern,
    paginate,
    parse_date_range,
    parse_optional_uuid,
)
from app.core.admin_security import AdminContext, require_permission
from app.db.session import get_db
from app.models.entities import AdminUser, AuditLog, User
from app.services.audit_service import AuditService

router = APIRouter()


def audit_row(a: AuditLog) -> dict:
    if a.admin_id is not None:
        actor = {"type": "admin", "id": str(a.admin_id),
                 "name": a.admin.full_name if a.admin else "Deleted admin", "email": a.admin.email if a.admin else None}
    elif a.actor_id is not None:
        actor = {"type": "user", "id": str(a.actor_id),
                 "name": a.actor.full_name if a.actor else "Deleted user", "email": a.actor.email if a.actor else None}
    else:
        actor = {"type": "system", "id": None, "name": "System", "email": None}
    return {
        "id": str(a.id),
        "action": a.action,
        "entity_type": a.entity_type,
        "entity_id": str(a.resource_id),
        "actor": actor,
        "details": a.details or {},
        # Only a prefix of the IP hash is shown: enough to correlate events from one address.
        "ip_hash": (a.ip_hash or "")[:12],
        "user_agent": a.user_agent,
        "created_at": iso(a.created_at),
    }


def _query(search, action, actor_type, admin_id, user_id, entity_type, entity_id, date_from, date_to):
    query = (
        select(AuditLog)
        .outerjoin(AdminUser, AdminUser.id == AuditLog.admin_id)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .options(joinedload(AuditLog.admin), joinedload(AuditLog.actor))
    )
    if action:
        actions = [a.strip().upper() for a in action.split(",") if a.strip()]
        query = query.where(AuditLog.action.in_(actions))
    if actor_type == "admin":
        query = query.where(AuditLog.admin_id.is_not(None))
    elif actor_type == "user":
        query = query.where(AuditLog.actor_id.is_not(None), AuditLog.admin_id.is_(None))
    elif actor_type:
        raise invalid("actor_type must be admin or user")
    if (aid := parse_optional_uuid(admin_id, "admin_id")):
        query = query.where(AuditLog.admin_id == aid)
    if (uid := parse_optional_uuid(user_id, "user_id")):
        query = query.where(or_(AuditLog.actor_id == uid, AuditLog.resource_id == uid))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if (eid := parse_optional_uuid(entity_id, "entity_id")):
        query = query.where(AuditLog.resource_id == eid)
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(
            func.lower(AuditLog.action).like(pattern, escape="\\"),
            func.lower(AdminUser.email).like(pattern, escape="\\"),
            func.lower(AdminUser.full_name).like(pattern, escape="\\"),
            func.lower(User.email).like(pattern, escape="\\"),
            func.lower(User.full_name).like(pattern, escape="\\"),
        ))
    start, end = parse_date_range(date_from, date_to)
    if start:
        query = query.where(AuditLog.created_at >= start)
    if end:
        query = query.where(AuditLog.created_at < end)
    return query


@router.get("")
def list_audit_logs(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    action: Optional[str] = Query(None, max_length=500),
    actor_type: Optional[str] = None,
    admin_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    _: AdminContext = Depends(require_permission("audit.view")),
    db: Session = Depends(get_db),
):
    query = _query(search, action, actor_type, admin_id, user_id, entity_type, entity_id, date_from, date_to)
    return paginate(db, query, page, [AuditLog.created_at.desc(), AuditLog.id], audit_row, unique=True)


@router.get("/facets")
def audit_facets(_: AdminContext = Depends(require_permission("audit.view")), db: Session = Depends(get_db)):
    actions = db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)).all()
    entity_types = db.scalars(select(AuditLog.entity_type).where(AuditLog.entity_type.is_not(None)).distinct()).all()
    return {"actions": actions, "entity_types": sorted(entity_types)}


@router.get("/export")
def export_audit_logs(
    request: Request,
    search: Optional[str] = Query(None, max_length=100),
    action: Optional[str] = Query(None, max_length=500),
    actor_type: Optional[str] = None,
    admin_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    ctx: AdminContext = Depends(require_permission("audit.view", "reports.export")),
    db: Session = Depends(get_db),
):
    query = _query(search, action, actor_type, admin_id, user_id, entity_type, entity_id, date_from, date_to)
    rows = [audit_row(a) for a in db.scalars(query.order_by(AuditLog.created_at.desc()).limit(EXPORT_ROW_LIMIT)).unique()]
    AuditService.record_admin(db, request, ctx.id, "EXPORT_AUDIT_LOG", "export", ctx.id, {"rows": len(rows)})
    db.commit()
    return csv_response(
        "audit-log.csv",
        ["created_at", "action", "actor_type", "actor_email", "entity_type", "entity_id", "details"],
        ([r["created_at"], r["action"], r["actor"]["type"], r["actor"]["email"], r["entity_type"], r["entity_id"],
          r["details"]] for r in rows),
    )
