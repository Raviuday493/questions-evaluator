"""Dashboard KPIs, time series, distributions and analytics reports -- all computed from live data."""
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import EXPORT_ROW_LIMIT, csv_response, invalid, iso, parse_date_range, parse_optional_uuid
from app.core.admin_security import AdminContext, require_permission, utcnow
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import (
    ANALYZED_STATUSES,
    IN_PROGRESS_STATUSES,
    AdminUser,
    AuditLog,
    Course,
    Department,
    PaperStatus,
    QPIReport,
    Question,
    QuestionPaperDraft,
    SimilarityMatch,
    User,
)
from app.services.audit_service import AuditService

router = APIRouter()

RANGES = {"today": 1, "7d": 7, "30d": 30, "90d": 90, "180d": 180, "365d": 365}


def resolve_range(range_key: str, date_from: Optional[date], date_to: Optional[date]) -> tuple:
    """Returns (start, end_exclusive, first_day, last_day)."""
    if range_key == "custom":
        if not date_from or not date_to:
            raise invalid("A custom range needs both 'from' and 'to'")
        if (date_to - date_from).days > 3 * 366:
            raise invalid("Custom ranges are limited to 3 years")
        start, end = parse_date_range(date_from, date_to)
        return start, end, date_from, date_to
    if range_key not in RANGES:
        raise invalid(f"range must be one of: {', '.join(list(RANGES) + ['custom'])}")
    last_day = utcnow().date()
    first_day = last_day - timedelta(days=RANGES[range_key] - 1)
    start, end = parse_date_range(first_day, last_day)
    return start, end, first_day, last_day


def _bucket_size(first: date, last: date) -> str:
    days = (last - first).days + 1
    if days <= 62:
        return "day"
    if days <= 200:
        return "week"
    return "month"


def _bucket_key(d: date, size: str) -> date:
    if size == "week":
        return d - timedelta(days=d.weekday())
    if size == "month":
        return d.replace(day=1)
    return d


def _empty_buckets(first: date, last: date, size: str) -> "OrderedDict[date, int]":
    buckets: "OrderedDict[date, int]" = OrderedDict()
    d = first
    while d <= last:
        buckets.setdefault(_bucket_key(d, size), 0)
        d += timedelta(days=1)
    return buckets


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _daily_counts(db: Session, column, start, end, *conditions) -> Dict[date, int]:
    """COUNT(*) grouped by UTC calendar day; `func.date` works on both PostgreSQL and SQLite."""
    day = func.date(column)
    rows = db.execute(
        select(day, func.count()).where(column >= start, column < end, *conditions).group_by(day)
    ).all()
    return {_as_date(d): n for d, n in rows if d is not None}


def _series(daily: Dict[date, int], first: date, last: date, size: str) -> List[int]:
    buckets = _empty_buckets(first, last, size)
    for d, n in daily.items():
        key = _bucket_key(d, size)
        if key in buckets:
            buckets[key] += n
    return list(buckets.values())


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard/summary")
def dashboard_summary(_: AdminContext = Depends(require_permission("dashboard.view")), db: Session = Depends(get_db)):
    now = utcnow()
    d30, d60 = now - timedelta(days=30), now - timedelta(days=60)
    today = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)

    def count(model_col, *conds) -> int:
        return db.scalar(select(func.count(model_col)).where(*conds)) or 0

    drafts = QuestionPaperDraft.is_historical_archive.is_(False)
    new_users_30 = count(User.id, User.created_at >= d30)
    new_users_prev = count(User.id, User.created_at >= d60, User.created_at < d30)
    uploads_30 = count(QuestionPaperDraft.id, drafts, QuestionPaperDraft.created_at >= d30)
    uploads_prev = count(QuestionPaperDraft.id, drafts, QuestionPaperDraft.created_at >= d60, QuestionPaperDraft.created_at < d30)
    avg_orig = db.scalar(
        select(func.avg(QPIReport.originality_score))
        .join(QuestionPaperDraft, QuestionPaperDraft.id == QPIReport.paper_id)
        .where(drafts, QuestionPaperDraft.status.in_(ANALYZED_STATUSES))
    )
    stuck_cutoff = now - timedelta(minutes=settings.STUCK_JOB_MINUTES)

    def change(cur: int, prev: int) -> Optional[float]:
        return round(100.0 * (cur - prev) / prev, 1) if prev else None

    return {
        "users": {
            "total": count(User.id),
            "active": count(User.id, User.is_active.is_(True)),
            "inactive": count(User.id, User.is_active.is_(False)),
            "new_30d": new_users_30,
            "new_30d_change_percent": change(new_users_30, new_users_prev),
            "signed_in_30d": count(User.id, User.last_login_at >= d30),
        },
        "papers": {
            "drafts_total": count(QuestionPaperDraft.id, drafts),
            "archive_total": count(QuestionPaperDraft.id, QuestionPaperDraft.is_historical_archive.is_(True)),
            "uploads_30d": uploads_30,
            "uploads_30d_change_percent": change(uploads_30, uploads_prev),
            "analyzed": count(QuestionPaperDraft.id, drafts, QuestionPaperDraft.status.in_(ANALYZED_STATUSES)),
            "approved": count(QuestionPaperDraft.id, QuestionPaperDraft.status == PaperStatus.APPROVED),
            "in_progress": count(QuestionPaperDraft.id, QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES)),
            "stuck": count(QuestionPaperDraft.id, QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES),
                           QuestionPaperDraft.updated_at < stuck_cutoff),
            "failed": count(QuestionPaperDraft.id, QuestionPaperDraft.status == PaperStatus.FAILED),
            "failed_7d": count(QuestionPaperDraft.id, QuestionPaperDraft.status == PaperStatus.FAILED,
                               QuestionPaperDraft.updated_at >= now - timedelta(days=7)),
            "avg_originality": round(float(avg_orig), 1) if avg_orig is not None else None,
        },
        "content": {
            "questions": count(Question.id),
            "matches": count(SimilarityMatch.id),
            "departments": count(Department.id),
            "courses": count(Course.id),
            "storage_bytes": int(db.scalar(select(func.coalesce(func.sum(QuestionPaperDraft.file_size_bytes), 0))) or 0),
        },
        "activity": {
            "events_today": count(AuditLog.id, AuditLog.created_at >= today),
            "user_logins_today": count(AuditLog.id, AuditLog.created_at >= today, AuditLog.action == "USER_LOGIN"),
            "admin_actions_today": count(AuditLog.id, AuditLog.created_at >= today, AuditLog.admin_id.is_not(None)),
        },
        "generated_at": iso(now),
    }


@router.get("/dashboard/timeseries")
def dashboard_timeseries(
    range_key: str = Query("30d", alias="range"),
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    _: AdminContext = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    start, end, first, last = resolve_range(range_key, date_from, date_to)
    size = _bucket_size(first, last)
    labels = [d.isoformat() for d in _empty_buckets(first, last, size)]
    created = QuestionPaperDraft.created_at
    drafts = QuestionPaperDraft.is_historical_archive.is_(False)
    return {
        "range": range_key,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "bucket": size,
        "labels": labels,
        "series": {
            "uploads": _series(_daily_counts(db, created, start, end, drafts), first, last, size),
            "archive_ingests": _series(_daily_counts(db, created, start, end, ~drafts), first, last, size),
            "failed": _series(_daily_counts(db, created, start, end, QuestionPaperDraft.status == PaperStatus.FAILED), first, last, size),
            "approvals": _series(_daily_counts(db, QuestionPaperDraft.approved_at, start, end), first, last, size),
            "signups": _series(_daily_counts(db, User.created_at, start, end), first, last, size),
            "logins": _series(_daily_counts(db, AuditLog.created_at, start, end, AuditLog.action == "USER_LOGIN"), first, last, size),
        },
    }


@router.get("/dashboard/distribution")
def dashboard_distribution(_: AdminContext = Depends(require_permission("dashboard.view")), db: Session = Depends(get_db)):
    status_rows = db.execute(select(QuestionPaperDraft.status, func.count()).group_by(QuestionPaperDraft.status)).all()
    tier_rows = db.execute(select(SimilarityMatch.match_tier, func.count()).group_by(SimilarityMatch.match_tier)).all()
    role_rows = db.execute(select(User.role, func.count()).group_by(User.role)).all()
    dept_rows = db.execute(
        select(Department.code, Department.name, func.count(QuestionPaperDraft.id))
        .join(Course, Course.department_id == Department.id)
        .join(QuestionPaperDraft, QuestionPaperDraft.course_id == Course.id)
        .group_by(Department.code, Department.name)
        .order_by(func.count(QuestionPaperDraft.id).desc())
    ).all()
    return {
        "paper_status": {s.value: n for s, n in status_rows},
        "match_tiers": {t.value: n for t, n in tier_rows},
        "user_roles": {r.value: n for r, n in role_rows},
        "papers_by_department": [{"code": c, "name": name, "count": n} for c, name, n in dept_rows],
    }


@router.get("/dashboard/activity")
def dashboard_activity(ctx: AdminContext = Depends(require_permission("dashboard.view")), db: Session = Depends(get_db)):
    signups = db.scalars(select(User).order_by(User.created_at.desc()).limit(6)).all() if ctx.can("users.view") else []
    papers = db.scalars(
        select(QuestionPaperDraft).options(joinedload(QuestionPaperDraft.course), joinedload(QuestionPaperDraft.uploader))
        .order_by(QuestionPaperDraft.created_at.desc()).limit(6)
    ).all() if ctx.can("papers.view") else []
    failures = db.scalars(
        select(QuestionPaperDraft).options(joinedload(QuestionPaperDraft.course))
        .where(QuestionPaperDraft.status == PaperStatus.FAILED)
        .order_by(QuestionPaperDraft.updated_at.desc()).limit(6)
    ).all() if ctx.can("papers.view") else []
    admin_actions = db.scalars(
        select(AuditLog).options(joinedload(AuditLog.admin)).where(AuditLog.admin_id.is_not(None))
        .order_by(AuditLog.created_at.desc()).limit(8)
    ).all() if ctx.can("audit.view") else []
    return {
        "recent_signups": [{"id": str(u.id), "full_name": u.full_name, "email": u.email, "role": u.role.value,
                            "created_at": iso(u.created_at)} for u in signups],
        "recent_uploads": [{"id": str(p.id), "course_code": p.course.code, "status": p.status.value,
                            "is_historical_archive": p.is_historical_archive,
                            "uploader_name": p.uploader.full_name if p.uploader else None,
                            "created_at": iso(p.created_at)} for p in papers],
        "recent_failures": [{"id": str(p.id), "course_code": p.course.code, "error_message": p.error_message,
                             "updated_at": iso(p.updated_at)} for p in failures],
        "recent_admin_actions": [{"id": str(a.id), "action": a.action, "entity_type": a.entity_type,
                                  "entity_id": str(a.resource_id),
                                  "admin_name": a.admin.full_name if a.admin else "Deleted admin",
                                  "created_at": iso(a.created_at)} for a in admin_actions],
    }


@router.get("/dashboard/alerts")
def dashboard_alerts(ctx: AdminContext = Depends(require_permission("dashboard.view")), db: Session = Depends(get_db)):
    """Items needing attention, shown in the header bell."""
    now = utcnow()
    alerts = []
    if ctx.can("papers.view"):
        stuck = db.scalar(select(func.count(QuestionPaperDraft.id)).where(
            QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES),
            QuestionPaperDraft.updated_at < now - timedelta(minutes=settings.STUCK_JOB_MINUTES))) or 0
        if stuck:
            alerts.append({"key": "stuck", "severity": "warning", "count": stuck,
                           "message": f"{stuck} analysis job(s) have made no progress for {settings.STUCK_JOB_MINUTES}+ minutes",
                           "link": "/papers?stuck=true"})
        failed = db.scalar(select(func.count(QuestionPaperDraft.id)).where(
            QuestionPaperDraft.status == PaperStatus.FAILED, QuestionPaperDraft.updated_at >= now - timedelta(days=1))) or 0
        if failed:
            alerts.append({"key": "failed", "severity": "error", "count": failed,
                           "message": f"{failed} analysis job(s) failed in the last 24 hours", "link": "/papers?status=FAILED"})
    if ctx.can("admins.view"):
        locked = db.scalar(select(func.count(AdminUser.id)).where(AdminUser.locked_until > now)) or 0
        if locked:
            alerts.append({"key": "locked_admins", "severity": "warning", "count": locked,
                           "message": f"{locked} admin account(s) are locked after failed sign-ins", "link": "/admins"})
    if ctx.can("audit.view"):
        failed_logins = db.scalar(select(func.count(AuditLog.id)).where(
            AuditLog.action == "ADMIN_LOGIN_FAILED", AuditLog.created_at >= now - timedelta(days=1))) or 0
        if failed_logins >= 3:
            alerts.append({"key": "admin_login_failures", "severity": "warning", "count": failed_logins,
                           "message": f"{failed_logins} failed admin sign-ins in the last 24 hours",
                           "link": "/audit-logs?action=ADMIN_LOGIN_FAILED"})
    return {"items": alerts, "count": len(alerts)}


# ------------------------------------------------------------------ reports
def _report_filters(start, end, department_id: Optional[str]):
    conds = [QuestionPaperDraft.created_at >= start, QuestionPaperDraft.created_at < end]
    dept = parse_optional_uuid(department_id, "department_id")
    if dept:
        conds.append(Course.department_id == dept)
    return conds


def _originality_by(db: Session, group_cols, conds):
    return db.execute(
        select(*group_cols, func.count(QuestionPaperDraft.id), func.avg(QPIReport.originality_score),
               func.min(QPIReport.originality_score), func.max(QPIReport.originality_score),
               func.coalesce(func.sum(QPIReport.matched_questions_count), 0))
        .select_from(QuestionPaperDraft)
        .join(Course, Course.id == QuestionPaperDraft.course_id)
        .join(Department, Department.id == Course.department_id)
        .join(QPIReport, QPIReport.paper_id == QuestionPaperDraft.id)
        .where(QuestionPaperDraft.is_historical_archive.is_(False), QuestionPaperDraft.status.in_(ANALYZED_STATUSES), *conds)
        .group_by(*group_cols)
        .order_by(func.count(QuestionPaperDraft.id).desc())
    ).all()


def _num(v, digits=1):
    return round(float(v), digits) if v is not None else None


def build_report(db: Session, start, end, department_id: Optional[str]) -> dict:
    conds = _report_filters(start, end, department_id)
    base_join = (
        select(QuestionPaperDraft.id).join(Course, Course.id == QuestionPaperDraft.course_id).where(*conds)
    )
    status_rows = db.execute(
        select(QuestionPaperDraft.status, func.count()).join(Course, Course.id == QuestionPaperDraft.course_id)
        .where(*conds).group_by(QuestionPaperDraft.status)
    ).all()
    by_dept = _originality_by(db, [Department.code, Department.name], conds)
    by_course = _originality_by(db, [Course.id, Course.code, Course.title, Department.code], conds)
    tier_rows = db.execute(
        select(SimilarityMatch.match_tier, func.count())
        .join(Question, Question.id == SimilarityMatch.draft_question_id)
        .where(Question.paper_id.in_(base_join))
        .group_by(SimilarityMatch.match_tier)
    ).all()
    blooms_rows = db.execute(
        select(Question.blooms_level, func.count()).where(Question.paper_id.in_(base_join), Question.blooms_level.is_not(None))
        .group_by(Question.blooms_level)
    ).all()
    type_rows = db.execute(
        select(Question.question_type, func.count()).where(Question.paper_id.in_(base_join), Question.question_type.is_not(None))
        .group_by(Question.question_type)
    ).all()
    uploader_rows = db.execute(
        select(User.id, User.full_name, User.email, func.count(QuestionPaperDraft.id), func.avg(QPIReport.originality_score))
        .select_from(QuestionPaperDraft)
        .join(User, User.id == QuestionPaperDraft.uploader_id)
        .join(Course, Course.id == QuestionPaperDraft.course_id)
        .outerjoin(QPIReport, QPIReport.paper_id == QuestionPaperDraft.id)
        .where(QuestionPaperDraft.is_historical_archive.is_(False), *conds)
        .group_by(User.id, User.full_name, User.email)
        .order_by(func.count(QuestionPaperDraft.id).desc())
        .limit(10)
    ).all()
    return {
        "status_breakdown": {s.value: n for s, n in status_rows},
        "match_tiers": {t.value: n for t, n in tier_rows},
        "blooms_levels": {b.value: n for b, n in blooms_rows},
        "question_types": {t.value: n for t, n in type_rows},
        "by_department": [
            {"code": code, "name": name, "papers": n, "avg_originality": _num(avg), "min_originality": _num(mn),
             "max_originality": _num(mx), "matched_questions": int(matched)}
            for code, name, n, avg, mn, mx, matched in by_dept
        ],
        "by_course": [
            {"course_id": str(cid), "code": code, "title": title, "department_code": dcode, "papers": n,
             "avg_originality": _num(avg), "min_originality": _num(mn), "max_originality": _num(mx),
             "matched_questions": int(matched)}
            for cid, code, title, dcode, n, avg, mn, mx, matched in by_course[:EXPORT_ROW_LIMIT]
        ],
        "top_uploaders": [
            {"user_id": str(uid), "full_name": name, "email": email, "papers": n, "avg_originality": _num(avg)}
            for uid, name, email, n, avg in uploader_rows
        ],
    }


@router.get("/reports/overview")
def report_overview(
    range_key: str = Query("90d", alias="range"),
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    department_id: Optional[str] = None,
    _: AdminContext = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
):
    start, end, first, last = resolve_range(range_key, date_from, date_to)
    return {"from": first.isoformat(), "to": last.isoformat(), **build_report(db, start, end, department_id)}


REPORT_EXPORTS = {
    "departments": (["department", "name", "analyzed_papers", "avg_originality", "min_originality", "max_originality", "matched_questions"],
                    lambda r: [[d["code"], d["name"], d["papers"], d["avg_originality"], d["min_originality"],
                                d["max_originality"], d["matched_questions"]] for d in r["by_department"]]),
    "courses": (["course", "title", "department", "analyzed_papers", "avg_originality", "min_originality", "max_originality", "matched_questions"],
                lambda r: [[c["code"], c["title"], c["department_code"], c["papers"], c["avg_originality"],
                            c["min_originality"], c["max_originality"], c["matched_questions"]] for c in r["by_course"]]),
    "uploaders": (["name", "email", "draft_papers", "avg_originality"],
                  lambda r: [[u["full_name"], u["email"], u["papers"], u["avg_originality"]] for u in r["top_uploaders"]]),
}


@router.get("/reports/{kind}/export")
def export_report(
    kind: str,
    request: Request,
    range_key: str = Query("90d", alias="range"),
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    department_id: Optional[str] = None,
    ctx: AdminContext = Depends(require_permission("reports.view", "reports.export")),
    db: Session = Depends(get_db),
):
    if kind not in REPORT_EXPORTS:
        raise HTTPException(status_code=404, detail="Report not found")
    start, end, first, last = resolve_range(range_key, date_from, date_to)
    headers, rows = REPORT_EXPORTS[kind]
    data = rows(build_report(db, start, end, department_id))
    AuditService.record_admin(db, request, ctx.id, "EXPORT_REPORT", "export", ctx.id,
                              {"report": kind, "from": first.isoformat(), "to": last.isoformat(), "rows": len(data)})
    db.commit()
    return csv_response(f"{kind}-report-{first.isoformat()}-to-{last.isoformat()}.csv", headers, data)
