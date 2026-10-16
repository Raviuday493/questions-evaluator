"""Runtime settings, system health, file storage overview and global search."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import Page, invalid, iso, like_pattern, paginate
from app.api.admin.papers import filtered_papers, paper_row
from app.core.admin_security import AdminContext, get_admin_context, require_permission, utcnow
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import (
    IN_PROGRESS_STATUSES,
    AdminUser,
    AppSetting,
    Course,
    Department,
    QuestionPaperDraft,
    User,
)
from app.schemas.admin import SettingsUpdateIn
from app.services.audit_service import AuditService
from app.services.embedding_provider import get_embedding_provider
from app.services.runtime_settings import (
    SETTING_BY_KEY,
    SETTING_DEFS,
    SettingValidationError,
    coerce,
    current_values,
    stored_values,
    validate_combination,
)

router = APIRouter()


# ------------------------------------------------------------------ settings
def _settings_payload(db: Session) -> list:
    values = current_values(db)
    rows = stored_values(db)
    admins = {}
    ids = [r.updated_by_id for r in rows.values() if r.updated_by_id]
    if ids:
        admins = {a.id: a.full_name for a in db.scalars(select(AdminUser).where(AdminUser.id.in_(ids)))}
    out = []
    for d in SETTING_DEFS:
        row = rows.get(d.key)
        out.append({
            "key": d.key, "label": d.label, "group": d.group, "type": d.type, "description": d.description,
            "value": values[d.key], "default": d.default(), "min": d.min, "max": d.max,
            "is_overridden": row is not None and row.value is not None,
            "updated_at": iso(row.updated_at) if row else None,
            "updated_by": admins.get(row.updated_by_id) if row else None,
        })
    return out


@router.get("/settings")
def get_settings(_: AdminContext = Depends(require_permission("settings.view")), db: Session = Depends(get_db)):
    return _settings_payload(db)


@router.put("/settings")
def update_settings(payload: SettingsUpdateIn, request: Request,
                    ctx: AdminContext = Depends(require_permission("settings.edit")), db: Session = Depends(get_db)):
    unknown = [k for k in payload.values if k not in SETTING_BY_KEY]
    if unknown:
        raise invalid(f"Unknown settings: {', '.join(unknown)}")
    current = current_values(db)
    proposed = dict(current)
    try:
        for key, raw in payload.values.items():
            # `null` resets a setting to its environment default.
            proposed[key] = SETTING_BY_KEY[key].default() if raw is None else coerce(SETTING_BY_KEY[key], raw)
        validate_combination(proposed)
    except SettingValidationError as exc:
        raise invalid(str(exc))
    rows = stored_values(db)
    changes = {}
    for key, raw in payload.values.items():
        row = rows.get(key)
        new_stored = None if raw is None else proposed[key]
        old_stored = row.value if row else None
        if new_stored == old_stored:
            continue
        changes[key] = [current[key], proposed[key]]
        if row is None:
            db.add(AppSetting(key=key, value=new_stored, updated_by_id=ctx.id))
        else:
            row.value, row.updated_by_id, row.updated_at = new_stored, ctx.id, utcnow()
    if changes:
        AuditService.record_admin(db, request, ctx.id, "SETTINGS_UPDATE", "settings", ctx.id, {"changes": changes})
        db.commit()
    return _settings_payload(db)


# ------------------------------------------------------------------ system
@router.get("/system/health")
def system_health(_: AdminContext = Depends(require_permission("system.view")), db: Session = Depends(get_db)):
    database, migration = "ok", None
    try:
        db.execute(text("SELECT 1"))
        try:
            migration = db.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            db.rollback()
    except Exception:
        database = "unavailable"
    try:
        embedding_model = get_embedding_provider().model_id
    except Exception:
        embedding_model = "unavailable"
    cutoff = utcnow() - timedelta(minutes=settings.STUCK_JOB_MINUTES)
    queue = {
        "in_progress": db.scalar(select(func.count(QuestionPaperDraft.id)).where(
            QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES))) or 0,
        "stuck": db.scalar(select(func.count(QuestionPaperDraft.id)).where(
            QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES), QuestionPaperDraft.updated_at < cutoff)) or 0,
    }
    # Only non-secret configuration is reported: no URLs, keys or credentials.
    return {
        "status": "healthy" if database == "ok" else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {"status": database, "dialect": db.get_bind().dialect.name, "migration": migration},
        "task_queue": {"backend": settings.TASK_QUEUE, **queue, "stuck_after_minutes": settings.STUCK_JOB_MINUTES},
        "embeddings": {"provider": settings.EMBEDDING_PROVIDER, "model": embedding_model, "dimension": settings.EMBEDDING_DIMENSION},
        "storage": {"type": settings.STORAGE_TYPE},
        "security": {
            "cookie_secure": settings.cookie_secure,
            "cors_origins": settings.cors_origins_list,
            "user_access_token_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "admin_session_idle_minutes": settings.ADMIN_SESSION_IDLE_MINUTES,
            "admin_session_max_hours": settings.ADMIN_SESSION_MAX_HOURS,
            "admin_lockout_after_failures": settings.ADMIN_MAX_FAILED_LOGINS,
        },
        "checked_at": iso(utcnow()),
    }


# ------------------------------------------------------------------ files
FILE_SORTS = {"created_at", "file_size_bytes"}


@router.get("/files")
def list_files(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    mime: Optional[str] = Query(None, pattern="^(pdf|docx)$"),
    uploader_id: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    sort: str = "created_at",
    order: str = Query("desc", pattern="^(asc|desc)$"),
    _: AdminContext = Depends(require_permission("papers.view")),
    db: Session = Depends(get_db),
):
    """Uploaded files are the papers' originals; storage keys/paths are never returned."""
    if sort not in FILE_SORTS:
        raise invalid(f"sort must be one of: {', '.join(sorted(FILE_SORTS))}")
    query = filtered_papers(search=search, uploader_id=uploader_id, date_from=date_from, date_to=date_to)
    if mime == "pdf":
        query = query.where(QuestionPaperDraft.file_mime_type == "application/pdf")
    elif mime == "docx":
        query = query.where(QuestionPaperDraft.file_mime_type != "application/pdf")
    column = getattr(QuestionPaperDraft, sort)
    result = paginate(
        db,
        query.options(joinedload(QuestionPaperDraft.course).joinedload(Course.department),
                      joinedload(QuestionPaperDraft.report), joinedload(QuestionPaperDraft.uploader)),
        page, [column.asc() if order == "asc" else column.desc(), QuestionPaperDraft.id], paper_row, unique=True,
    )
    totals = db.execute(
        select(QuestionPaperDraft.file_mime_type, func.count(QuestionPaperDraft.id),
               func.coalesce(func.sum(QuestionPaperDraft.file_size_bytes), 0))
        .group_by(QuestionPaperDraft.file_mime_type)
    ).all()
    result["summary"] = {
        "total_files": sum(n for _, n, _ in totals),
        "total_bytes": int(sum(b for _, _, b in totals)),
        "by_type": [{"mime_type": m, "count": n, "bytes": int(b)} for m, n, b in totals],
        "storage_type": settings.STORAGE_TYPE,
    }
    return result


# ------------------------------------------------------------------ search
@router.get("/search")
def global_search(
    q: str = Query(..., min_length=2, max_length=100),
    ctx: AdminContext = Depends(get_admin_context),
    db: Session = Depends(get_db),
):
    pattern = like_pattern(q)
    results = {}
    if ctx.can("users.view"):
        users = db.scalars(select(User).where(or_(
            func.lower(User.email).like(pattern, escape="\\"), func.lower(User.full_name).like(pattern, escape="\\")
        )).order_by(User.full_name).limit(5))
        results["users"] = [{"id": str(u.id), "title": u.full_name, "subtitle": u.email} for u in users]
    if ctx.can("papers.view"):
        papers = db.scalars(filtered_papers(search=q).options(joinedload(QuestionPaperDraft.course))
                            .order_by(QuestionPaperDraft.created_at.desc()).limit(5)).unique()
        results["papers"] = [{"id": str(p.id), "title": f"{p.course.code} · {p.term} {p.academic_year}",
                              "subtitle": f"{p.exam_type} · {p.original_filename} · {p.status.value}"} for p in papers]
    if ctx.can("catalog.view"):
        courses = db.scalars(select(Course).options(joinedload(Course.department)).where(or_(
            func.lower(Course.code).like(pattern, escape="\\"), func.lower(Course.title).like(pattern, escape="\\")
        )).order_by(Course.code).limit(5))
        results["courses"] = [{"id": str(c.id), "title": c.code, "subtitle": f"{c.title} · {c.department.code}"} for c in courses]
        depts = db.scalars(select(Department).where(or_(
            func.lower(Department.code).like(pattern, escape="\\"), func.lower(Department.name).like(pattern, escape="\\")
        )).limit(5))
        results["departments"] = [{"id": str(d.id), "title": d.name, "subtitle": d.code} for d in depts]
    if ctx.can("admins.view"):
        admins = db.scalars(select(AdminUser).where(or_(
            func.lower(AdminUser.email).like(pattern, escape="\\"), func.lower(AdminUser.full_name).like(pattern, escape="\\")
        )).limit(5))
        results["admins"] = [{"id": str(a.id), "title": a.full_name, "subtitle": a.email} for a in admins]
    return results
