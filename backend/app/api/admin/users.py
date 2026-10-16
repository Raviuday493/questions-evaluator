"""Application-user management (faculty, department heads, archival and system admins of the main app)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import (
    EXPORT_ROW_LIMIT,
    Page,
    conflict,
    csv_response,
    invalid,
    iso,
    like_pattern,
    not_found,
    paginate,
    parse_bool_filter,
    parse_date_range,
    parse_enum_list,
    parse_id,
    parse_optional_uuid,
)
from app.core.admin_security import AdminContext, require_permission, utcnow
from app.core.security import hash_password
from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    Department,
    PaperStatus,
    QPIReport,
    QuestionPaperDraft,
    User,
    UserRole,
)
from app.schemas.admin import BulkUserActionIn, PasswordResetIn, StatusChangeIn, UserCreateIn, UserUpdateIn
from app.services.audit_service import AuditService

router = APIRouter()

SORTS = {
    "created_at": User.created_at,
    "full_name": User.full_name,
    "email": User.email,
    "role": User.role,
    "last_login_at": User.last_login_at,
}


def _department(d: Optional[Department]) -> Optional[dict]:
    return {"id": str(d.id), "code": d.code, "name": d.name} if d else None


def user_row(user: User, paper_count: int = 0) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "department": _department(user.department),
        "is_active": user.is_active,
        "last_login_at": iso(user.last_login_at),
        "sessions_invalidated_at": iso(user.sessions_invalidated_at),
        "created_at": iso(user.created_at),
        "updated_at": iso(user.updated_at),
        "paper_count": paper_count,
    }


def _filtered_query(search, role, department_id, active, date_from, date_to):
    query = select(User).outerjoin(Department, Department.id == User.department_id)
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(
            func.lower(User.email).like(pattern, escape="\\"),
            func.lower(User.full_name).like(pattern, escape="\\"),
        ))
    roles = parse_enum_list(role, UserRole, "role")
    if roles:
        query = query.where(User.role.in_(roles))
    dept = parse_optional_uuid(department_id, "department_id")
    if dept:
        query = query.where(User.department_id == dept)
    is_active = parse_bool_filter(active, "active")
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))
    start, end = parse_date_range(date_from, date_to)
    if start:
        query = query.where(User.created_at >= start)
    if end:
        query = query.where(User.created_at < end)
    return query


def _paper_counts(db: Session, user_ids) -> dict:
    if not user_ids:
        return {}
    rows = db.execute(
        select(QuestionPaperDraft.uploader_id, func.count(QuestionPaperDraft.id))
        .where(QuestionPaperDraft.uploader_id.in_(user_ids))
        .group_by(QuestionPaperDraft.uploader_id)
    )
    return {uid: n for uid, n in rows}


def _get_user(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).options(joinedload(User.department)).where(User.id == parse_id(user_id, "User")))
    if user is None:
        raise not_found("User")
    return user


@router.get("")
def list_users(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None, description="Comma-separated roles"),
    department_id: Optional[str] = None,
    active: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    sort: str = "created_at",
    order: str = Query("desc", pattern="^(asc|desc)$"),
    _: AdminContext = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    if sort not in SORTS:
        raise invalid(f"sort must be one of: {', '.join(SORTS)}")
    query = _filtered_query(search, role, department_id, active, date_from, date_to).options(joinedload(User.department))
    column = SORTS[sort]
    ordering = column.asc() if order == "asc" else column.desc()
    if sort == "last_login_at":
        ordering = ordering.nulls_last()
    result = paginate(db, query, page, [ordering, User.id], lambda u: u)
    counts = _paper_counts(db, [u.id for u in result["items"]])
    result["items"] = [user_row(u, counts.get(u.id, 0)) for u in result["items"]]
    return result


@router.get("/export")
def export_users(
    request: Request,
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = None,
    department_id: Optional[str] = None,
    active: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    ctx: AdminContext = Depends(require_permission("users.view", "reports.export")),
    db: Session = Depends(get_db),
):
    query = _filtered_query(search, role, department_id, active, date_from, date_to).options(joinedload(User.department))
    users = db.scalars(query.order_by(User.created_at.desc()).limit(EXPORT_ROW_LIMIT)).all()
    counts = _paper_counts(db, [u.id for u in users])
    AuditService.record_admin(db, request, ctx.id, "EXPORT_USERS", "export", ctx.id, {"rows": len(users)})
    db.commit()
    return csv_response(
        "users.csv",
        ["id", "email", "full_name", "role", "department", "active", "papers", "last_login_at", "created_at"],
        ([u.id, u.email, u.full_name, u.role.value, u.department.code if u.department else "", u.is_active,
          counts.get(u.id, 0), iso(u.last_login_at), iso(u.created_at)] for u in users),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateIn,
    request: Request,
    ctx: AdminContext = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise conflict("An account with this email already exists")
    if payload.department_id and db.get(Department, payload.department_id) is None:
        raise invalid("Unknown department")
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        department_id=payload.department_id,
    )
    db.add(user)
    db.flush()
    AuditService.record_admin(db, request, ctx.id, "USER_CREATE", "user", user.id,
                              {"email": email, "role": payload.role.value})
    db.commit()
    return user_row(_get_user(db, str(user.id)))


@router.post("/bulk")
def bulk_action(
    payload: BulkUserActionIn,
    request: Request,
    ctx: AdminContext = Depends(require_permission("users.status")),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).where(User.id.in_(payload.ids))).all()
    now = utcnow()
    changed = 0
    for user in users:
        if payload.action == "activate" and not user.is_active:
            user.is_active = True
        elif payload.action == "deactivate" and user.is_active:
            user.is_active = False
            user.sessions_invalidated_at = now
        elif payload.action == "revoke_sessions":
            user.sessions_invalidated_at = now
        else:
            continue
        changed += 1
        AuditService.record_admin(db, request, ctx.id, f"USER_{payload.action.upper()}", "user", user.id,
                                  {"bulk": True, "reason": payload.reason})
    db.commit()
    return {"requested": len(payload.ids), "found": len(users), "changed": changed}


@router.get("/{user_id}")
def get_user(user_id: str, ctx: AdminContext = Depends(require_permission("users.view")), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    status_rows = db.execute(
        select(QuestionPaperDraft.status, func.count(QuestionPaperDraft.id))
        .where(QuestionPaperDraft.uploader_id == user.id)
        .group_by(QuestionPaperDraft.status)
    )
    by_status = {s.value: n for s, n in status_rows}
    avg_originality = db.scalar(
        select(func.avg(QPIReport.originality_score))
        .join(QuestionPaperDraft, QuestionPaperDraft.id == QPIReport.paper_id)
        .where(QuestionPaperDraft.uploader_id == user.id, QuestionPaperDraft.is_historical_archive.is_(False))
    )
    last_activity = db.scalar(select(func.max(AuditLog.created_at)).where(AuditLog.actor_id == user.id))
    papers = db.scalars(
        select(QuestionPaperDraft)
        .options(joinedload(QuestionPaperDraft.course), joinedload(QuestionPaperDraft.report))
        .where(QuestionPaperDraft.uploader_id == user.id)
        .order_by(QuestionPaperDraft.created_at.desc())
        .limit(10)
    ).unique().all()
    activity = db.scalars(
        select(AuditLog).where(AuditLog.actor_id == user.id).order_by(AuditLog.created_at.desc()).limit(15)
    ).all()
    admin_actions = db.scalars(
        select(AuditLog).options(joinedload(AuditLog.admin))
        .where(AuditLog.resource_id == user.id, AuditLog.admin_id.is_not(None))
        .order_by(AuditLog.created_at.desc())
        .limit(15)
    ).all() if ctx.can("audit.view") else []
    total = sum(by_status.values())
    return {
        **user_row(user, total),
        "stats": {
            "papers_total": total,
            "papers_by_status": by_status,
            "approved": by_status.get(PaperStatus.APPROVED.value, 0),
            "failed": by_status.get(PaperStatus.FAILED.value, 0),
            "avg_originality": round(float(avg_originality), 1) if avg_originality is not None else None,
            "last_activity_at": iso(last_activity),
        },
        "recent_papers": [
            {
                "id": str(p.id),
                "course_code": p.course.code,
                "academic_year": p.academic_year,
                "term": p.term,
                "exam_type": p.exam_type,
                "status": p.status.value,
                "is_historical_archive": p.is_historical_archive,
                "originality_score": float(p.report.originality_score) if p.report else None,
                "created_at": iso(p.created_at),
            }
            for p in papers
        ],
        "recent_activity": [
            {"id": str(a.id), "action": a.action, "resource_id": str(a.resource_id), "details": a.details,
             "created_at": iso(a.created_at)}
            for a in activity
        ],
        "admin_actions": [
            {"id": str(a.id), "action": a.action, "details": a.details, "created_at": iso(a.created_at),
             "admin_name": a.admin.full_name if a.admin else None}
            for a in admin_actions
        ],
    }


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdateIn,
    request: Request,
    ctx: AdminContext = Depends(require_permission("users.edit")),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    changes = {}
    if payload.email is not None and payload.email.lower() != user.email:
        email = payload.email.lower()
        if db.scalar(select(User.id).where(func.lower(User.email) == email, User.id != user.id)):
            raise conflict("Another account already uses this email")
        changes["email"] = [user.email, email]
        user.email = email
    if payload.full_name is not None and payload.full_name != user.full_name:
        changes["full_name"] = [user.full_name, payload.full_name]
        user.full_name = payload.full_name
    if payload.role is not None and payload.role != user.role:
        changes["role"] = [user.role.value, payload.role.value]
        user.role = payload.role
        # Role changes take effect immediately: tokens carry the old role claim.
        user.sessions_invalidated_at = utcnow()
    if payload.clear_department:
        if user.department_id is not None:
            changes["department"] = [user.department.code if user.department else None, None]
            user.department_id = None
    elif payload.department_id is not None and payload.department_id != user.department_id:
        dept = db.get(Department, payload.department_id)
        if dept is None:
            raise invalid("Unknown department")
        changes["department"] = [user.department.code if user.department else None, dept.code]
        user.department_id = dept.id
    if user.role == UserRole.DEPT_HEAD and user.department_id is None:
        raise invalid("A department head must belong to a department")
    if changes:
        AuditService.record_admin(db, request, ctx.id, "USER_UPDATE", "user", user.id, {"changes": changes})
        db.commit()
        db.expire(user)
    return user_row(_get_user(db, user_id), db.scalar(
        select(func.count(QuestionPaperDraft.id)).where(QuestionPaperDraft.uploader_id == user.id)) or 0)


def _set_active(db: Session, request: Request, ctx: AdminContext, user_id: str, active: bool, reason: Optional[str]):
    user = _get_user(db, user_id)
    if user.is_active == active:
        raise conflict(f"User is already {'active' if active else 'inactive'}")
    user.is_active = active
    if not active:
        user.sessions_invalidated_at = utcnow()
    AuditService.record_admin(db, request, ctx.id, "USER_ACTIVATE" if active else "USER_DEACTIVATE", "user", user.id,
                              {"reason": reason})
    db.commit()
    return user_row(_get_user(db, user_id))


@router.post("/{user_id}/activate")
def activate_user(user_id: str, payload: StatusChangeIn, request: Request,
                  ctx: AdminContext = Depends(require_permission("users.status")), db: Session = Depends(get_db)):
    return _set_active(db, request, ctx, user_id, True, payload.reason)


@router.post("/{user_id}/deactivate")
def deactivate_user(user_id: str, payload: StatusChangeIn, request: Request,
                    ctx: AdminContext = Depends(require_permission("users.status")), db: Session = Depends(get_db)):
    return _set_active(db, request, ctx, user_id, False, payload.reason)


@router.post("/{user_id}/revoke-sessions")
def revoke_user_sessions(user_id: str, request: Request,
                         ctx: AdminContext = Depends(require_permission("users.status")), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    user.sessions_invalidated_at = utcnow()
    AuditService.record_admin(db, request, ctx.id, "USER_REVOKE_SESSIONS", "user", user.id)
    db.commit()
    return user_row(_get_user(db, user_id))


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(user_id: str, payload: PasswordResetIn, request: Request,
                        ctx: AdminContext = Depends(require_permission("users.edit")), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    user.sessions_invalidated_at = utcnow()
    AuditService.record_admin(db, request, ctx.id, "USER_PASSWORD_RESET", "user", user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, request: Request,
                ctx: AdminContext = Depends(require_permission("users.delete")), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    papers = db.scalar(select(func.count(QuestionPaperDraft.id)).where(QuestionPaperDraft.uploader_id == user.id)) or 0
    if papers:
        raise conflict(
            f"This user owns {papers} paper(s), which are part of the analysis history. Deactivate the account instead."
        )
    snapshot = {"email": user.email, "full_name": user.full_name, "role": user.role.value}
    db.delete(user)
    AuditService.record_admin(db, request, ctx.id, "USER_DELETE", "user", user.id, snapshot)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
