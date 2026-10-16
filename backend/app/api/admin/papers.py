"""Question papers (drafts and historical archive), their analyses and uploaded files."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

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
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import (
    IN_PROGRESS_STATUSES,
    Course,
    PaperStatus,
    QPIReport,
    Question,
    QuestionPaperDraft,
    SimilarityMatch,
    User,
)
from app.schemas.admin import BulkPaperActionIn, MarkFailedIn
from app.services.audit_service import AuditService
from app.services.paper_pipeline import dispatch_processing
from app.services.storage_service import get_storage_provider

router = APIRouter()

SORTS = {
    "created_at": QuestionPaperDraft.created_at,
    "updated_at": QuestionPaperDraft.updated_at,
    "academic_year": QuestionPaperDraft.academic_year,
    "status": QuestionPaperDraft.status,
    "course_code": Course.code,
    "originality_score": QPIReport.originality_score,
    "file_size_bytes": QuestionPaperDraft.file_size_bytes,
}
PROCESSING = (PaperStatus.PARSING, PaperStatus.EMBEDDING, PaperStatus.MATCHING)


def _is_stuck(paper: QuestionPaperDraft) -> bool:
    if paper.status not in IN_PROGRESS_STATUSES:
        return False
    updated = paper.updated_at if paper.updated_at.tzinfo else paper.updated_at.replace(tzinfo=timezone.utc)
    return updated < utcnow() - timedelta(minutes=settings.STUCK_JOB_MINUTES)


def paper_row(p: QuestionPaperDraft) -> dict:
    report = p.report
    dept = p.course.department if p.course else None
    return {
        "id": str(p.id),
        "course": {"id": str(p.course.id), "code": p.course.code, "title": p.course.title} if p.course else None,
        "department": {"id": str(dept.id), "code": dept.code, "name": dept.name} if dept else None,
        "uploader": {"id": str(p.uploader.id), "full_name": p.uploader.full_name, "email": p.uploader.email} if p.uploader else None,
        "academic_year": p.academic_year,
        "term": p.term,
        "exam_type": p.exam_type,
        "total_marks": p.total_marks,
        "original_filename": p.original_filename,
        "file_mime_type": p.file_mime_type,
        "file_size_bytes": p.file_size_bytes,
        "is_historical_archive": p.is_historical_archive,
        "status": p.status.value,
        "progress_percent": p.progress_percent,
        "current_step": p.current_step,
        "error_message": p.error_message,
        "is_stuck": _is_stuck(p),
        "previous_paper_id": str(p.previous_paper_id) if p.previous_paper_id else None,
        "report_id": str(report.id) if report else None,
        "originality_score": float(report.originality_score) if report else None,
        "total_questions": report.total_questions if report else None,
        "matched_questions_count": report.matched_questions_count if report else None,
        "approved_at": iso(p.approved_at),
        "created_at": iso(p.created_at),
        "updated_at": iso(p.updated_at),
    }


_LIST_OPTIONS = (
    joinedload(QuestionPaperDraft.course).joinedload(Course.department),
    joinedload(QuestionPaperDraft.report),
    joinedload(QuestionPaperDraft.uploader),
)


def filtered_papers(
    search=None, status_filter=None, department_id=None, course_id=None, uploader_id=None, archive=None,
    date_from=None, date_to=None, stuck=None,
):
    query = (
        select(QuestionPaperDraft)
        .join(Course, Course.id == QuestionPaperDraft.course_id)
        .join(User, User.id == QuestionPaperDraft.uploader_id)
        .outerjoin(QPIReport, QPIReport.paper_id == QuestionPaperDraft.id)
    )
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(
            func.lower(Course.code).like(pattern, escape="\\"),
            func.lower(Course.title).like(pattern, escape="\\"),
            func.lower(QuestionPaperDraft.original_filename).like(pattern, escape="\\"),
            func.lower(QuestionPaperDraft.exam_type).like(pattern, escape="\\"),
            func.lower(QuestionPaperDraft.academic_year).like(pattern, escape="\\"),
            func.lower(User.full_name).like(pattern, escape="\\"),
            func.lower(User.email).like(pattern, escape="\\"),
        ))
    statuses = parse_enum_list(status_filter, PaperStatus, "status")
    if statuses:
        query = query.where(QuestionPaperDraft.status.in_(statuses))
    dept = parse_optional_uuid(department_id, "department_id")
    if dept:
        query = query.where(Course.department_id == dept)
    course = parse_optional_uuid(course_id, "course_id")
    if course:
        query = query.where(QuestionPaperDraft.course_id == course)
    uploader = parse_optional_uuid(uploader_id, "uploader_id")
    if uploader:
        query = query.where(QuestionPaperDraft.uploader_id == uploader)
    is_archive = parse_bool_filter(archive, "archive")
    if is_archive is not None:
        query = query.where(QuestionPaperDraft.is_historical_archive.is_(is_archive))
    start, end = parse_date_range(date_from, date_to)
    if start:
        query = query.where(QuestionPaperDraft.created_at >= start)
    if end:
        query = query.where(QuestionPaperDraft.created_at < end)
    if parse_bool_filter(stuck, "stuck"):
        cutoff = utcnow() - timedelta(minutes=settings.STUCK_JOB_MINUTES)
        query = query.where(QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES), QuestionPaperDraft.updated_at < cutoff)
    return query


def _get_paper(db: Session, paper_id: str) -> QuestionPaperDraft:
    paper = db.scalar(select(QuestionPaperDraft).options(*_LIST_OPTIONS).where(QuestionPaperDraft.id == parse_id(paper_id, "Paper")))
    if paper is None:
        raise not_found("Paper")
    return paper


@router.get("")
def list_papers(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    department_id: Optional[str] = None,
    course_id: Optional[str] = None,
    uploader_id: Optional[str] = None,
    archive: Optional[str] = None,
    stuck: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    sort: str = "created_at",
    order: str = Query("desc", pattern="^(asc|desc)$"),
    _: AdminContext = Depends(require_permission("papers.view")),
    db: Session = Depends(get_db),
):
    if sort not in SORTS:
        raise invalid(f"sort must be one of: {', '.join(SORTS)}")
    query = filtered_papers(search, status_filter, department_id, course_id, uploader_id, archive, date_from, date_to, stuck)
    column = SORTS[sort]
    ordering = column.asc() if order == "asc" else column.desc()
    if sort == "originality_score":
        ordering = ordering.nulls_last()
    return paginate(db, query.options(*_LIST_OPTIONS), page, [ordering, QuestionPaperDraft.id], paper_row, unique=True)


@router.get("/export")
def export_papers(
    request: Request,
    search: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    department_id: Optional[str] = None,
    course_id: Optional[str] = None,
    uploader_id: Optional[str] = None,
    archive: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    ctx: AdminContext = Depends(require_permission("papers.view", "reports.export")),
    db: Session = Depends(get_db),
):
    query = filtered_papers(search, status_filter, department_id, course_id, uploader_id, archive, date_from, date_to)
    papers = db.scalars(query.options(*_LIST_OPTIONS).order_by(QuestionPaperDraft.created_at.desc()).limit(EXPORT_ROW_LIMIT)).unique().all()
    AuditService.record_admin(db, request, ctx.id, "EXPORT_PAPERS", "export", ctx.id, {"rows": len(papers)})
    db.commit()
    return csv_response(
        "papers.csv",
        ["id", "course", "department", "academic_year", "term", "exam_type", "total_marks", "status", "archive",
         "originality_score", "questions", "matched_questions", "uploader_email", "filename", "size_bytes", "created_at"],
        ([p.id, p.course.code, p.course.department.code if p.course.department else "", p.academic_year, p.term,
          p.exam_type, p.total_marks, p.status.value, p.is_historical_archive,
          float(p.report.originality_score) if p.report else "", p.report.total_questions if p.report else "",
          p.report.matched_questions_count if p.report else "", p.uploader.email if p.uploader else "",
          p.original_filename, p.file_size_bytes, iso(p.created_at)] for p in papers),
    )


@router.post("/bulk")
def bulk_action(
    payload: BulkPaperActionIn,
    request: Request,
    background_tasks: BackgroundTasks,
    ctx: AdminContext = Depends(require_permission("papers.view")),
    db: Session = Depends(get_db),
):
    needed = "papers.manage" if payload.action == "reanalyze" else "papers.delete"
    if not ctx.can(needed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You do not have permission to perform this action ({needed})")
    papers = db.scalars(select(QuestionPaperDraft).where(QuestionPaperDraft.id.in_(payload.ids))).all()
    done, skipped, files_to_delete, to_dispatch = [], [], [], []
    for paper in papers:
        if payload.action == "reanalyze":
            if _can_reanalyze(paper):
                _queue(paper)
                to_dispatch.append(str(paper.id))
                done.append(str(paper.id))
                AuditService.record_admin(db, request, ctx.id, "PAPER_REANALYZE", "paper", paper.id, {"bulk": True})
            else:
                skipped.append({"id": str(paper.id), "reason": f"Status {paper.status.value} cannot be re-analysed"})
        else:
            if paper.status in PROCESSING:
                skipped.append({"id": str(paper.id), "reason": "Currently being analysed"})
                continue
            files_to_delete.append(paper.file_path)
            AuditService.record_admin(db, request, ctx.id, "PAPER_DELETE", "paper", paper.id,
                                      {"bulk": True, "filename": paper.original_filename})
            db.delete(paper)
            done.append(str(paper.id))
    db.commit()
    storage = get_storage_provider()
    for path in files_to_delete:
        storage.delete_file(path)
    for paper_id in to_dispatch:
        dispatch_processing(paper_id, background_tasks)
    missing = len(payload.ids) - len(papers)
    return {"done": done, "skipped": skipped, "not_found": missing}


def _can_reanalyze(paper: QuestionPaperDraft) -> bool:
    # Mirrors the application rule: re-analysing an archived paper would drop matches other reports reference.
    return paper.status == PaperStatus.FAILED or (paper.status == PaperStatus.COMPLETED and not paper.is_historical_archive)


def _queue(paper: QuestionPaperDraft) -> None:
    paper.status = PaperStatus.QUEUED
    paper.progress_percent = 0
    paper.current_step = "Queued for analysis"
    paper.error_message = None


@router.get("/{paper_id}")
def get_paper(paper_id: str, _: AdminContext = Depends(require_permission("papers.view")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    report = db.scalar(
        select(QPIReport).options(selectinload(QPIReport.recommendations)).where(QPIReport.paper_id == paper.id)
    )
    questions = db.scalars(
        select(Question).options(joinedload(Question.unit)).where(Question.paper_id == paper.id).order_by(Question.position)
    ).all()
    best = {}
    if questions:
        rows = db.scalars(
            select(SimilarityMatch)
            .options(joinedload(SimilarityMatch.historical_question).joinedload(Question.paper).joinedload(QuestionPaperDraft.course))
            .where(SimilarityMatch.draft_question_id.in_([q.id for q in questions]))
            .order_by(SimilarityMatch.composite_score.desc())
        ).all()
        for m in rows:
            best.setdefault(m.draft_question_id, m)
    revisions = db.scalars(
        select(QuestionPaperDraft).where(QuestionPaperDraft.previous_paper_id == paper.id).order_by(QuestionPaperDraft.created_at)
    ).all()
    # How often this paper's questions were matched by other drafts (only meaningful for archive papers).
    times_matched = db.scalar(
        select(func.count(SimilarityMatch.id))
        .join(Question, Question.id == SimilarityMatch.historical_question_id)
        .where(Question.paper_id == paper.id)
    ) or 0

    def question_payload(q: Question) -> dict:
        m = best.get(q.id)
        return {
            "id": str(q.id),
            "question_number": q.question_number,
            "section_name": q.section_name,
            "text": q.clean_text,
            "marks": q.marks,
            "question_type": q.question_type.value if q.question_type else None,
            "blooms_level": q.blooms_level.value if q.blooms_level else None,
            "unit": {"unit_number": q.unit.unit_number, "title": q.unit.title} if q.unit else None,
            "is_sub_question": q.parent_question_id is not None,
            "best_match": {
                "match_tier": m.match_tier.value,
                "composite_score": float(m.composite_score),
                "source_paper_id": str(m.historical_question.paper_id),
                "source_label": f"{m.historical_question.paper.course.code} {m.historical_question.paper.academic_year} "
                                f"{m.historical_question.paper.term} Q{m.historical_question.question_number}",
            } if m else None,
        }

    scan = (report.scan_metadata_json or {}) if report else {}
    return {
        **paper_row(paper),
        "approved_by": {"id": str(paper.approved_by.id), "full_name": paper.approved_by.full_name} if paper.approved_by else None,
        "report": {
            "id": str(report.id),
            "originality_score": float(report.originality_score),
            "total_questions": report.total_questions,
            "matched_questions_count": report.matched_questions_count,
            "severity_breakdown": scan.get("severity_breakdown", {}),
            "scan": {k: v for k, v in scan.items() if k != "severity_breakdown"},
            "blooms_distribution": report.blooms_distribution_json,
            "question_types": report.question_type_json,
            "unit_coverage": report.unit_coverage_json,
            "processing_seconds": report.processing_seconds,
            "generated_at": iso(report.generated_at),
            "recommendations": [
                {"priority": r.priority, "category": r.category.value, "action_text": r.action_text, "rationale": r.rationale}
                for r in report.recommendations
            ],
        } if report else None,
        "questions": [question_payload(q) for q in questions],
        "revisions": [{"id": str(r.id), "status": r.status.value, "created_at": iso(r.created_at)} for r in revisions],
        "times_matched_by_other_drafts": times_matched,
        "can_reanalyze": _can_reanalyze(paper),
        "can_approve": paper.status == PaperStatus.COMPLETED,
        "can_delete": paper.status not in PROCESSING,
        "can_mark_failed": paper.status in IN_PROGRESS_STATUSES,
    }


@router.get("/{paper_id}/file")
def download_file(paper_id: str, request: Request,
                  ctx: AdminContext = Depends(require_permission("papers.download")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    try:
        content = get_storage_provider().get_file(paper.file_path)
    except FileNotFoundError:
        raise not_found("Stored file")
    AuditService.record_admin(db, request, ctx.id, "PAPER_DOWNLOAD", "paper", paper.id)
    db.commit()
    return Response(
        content=content,
        media_type=paper.file_mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(paper.original_filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post("/{paper_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(paper_id: str, request: Request, background_tasks: BackgroundTasks,
              ctx: AdminContext = Depends(require_permission("papers.manage")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    if not _can_reanalyze(paper):
        detail = f"A paper with status {paper.status.value} cannot be re-analysed"
        if paper.is_historical_archive and paper.status == PaperStatus.COMPLETED:
            detail = "Archive papers cannot be re-analysed: other reports reference their questions"
        raise conflict(detail)
    _queue(paper)
    AuditService.record_admin(db, request, ctx.id, "PAPER_REANALYZE", "paper", paper.id)
    db.commit()
    dispatch_processing(str(paper.id), background_tasks)
    return paper_row(_get_paper(db, paper_id))


@router.post("/{paper_id}/approve")
def approve(paper_id: str, request: Request,
            ctx: AdminContext = Depends(require_permission("papers.manage")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    if paper.status != PaperStatus.COMPLETED:
        raise conflict("Only completed analyses can be approved")
    paper.status = PaperStatus.APPROVED
    paper.approved_at = datetime.now(timezone.utc)
    paper.approved_by_id = None  # approved_by references application users; the admin is recorded in the audit log
    paper.current_step = "Approved for exam archive"
    AuditService.record_admin(db, request, ctx.id, "PAPER_APPROVE", "paper", paper.id)
    db.commit()
    return paper_row(_get_paper(db, paper_id))


@router.post("/{paper_id}/mark-failed")
def mark_failed(paper_id: str, payload: MarkFailedIn, request: Request,
                ctx: AdminContext = Depends(require_permission("papers.manage")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    if paper.status not in IN_PROGRESS_STATUSES:
        raise conflict("Only queued or in-progress analyses can be marked as failed")
    previous = paper.status.value
    paper.status = PaperStatus.FAILED
    paper.current_step = "Analysis failed"
    paper.error_message = payload.reason
    AuditService.record_admin(db, request, ctx.id, "PAPER_MARK_FAILED", "paper", paper.id,
                              {"previous_status": previous, "reason": payload.reason})
    db.commit()
    return paper_row(_get_paper(db, paper_id))


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(paper_id: str, request: Request,
           ctx: AdminContext = Depends(require_permission("papers.delete")), db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    if paper.status in PROCESSING:
        raise conflict("This paper is currently being analysed; try again when it finishes")
    file_path = paper.file_path
    AuditService.record_admin(db, request, ctx.id, "PAPER_DELETE", "paper", paper.id, {
        "filename": paper.original_filename, "course": paper.course.code, "status": paper.status.value,
        "archive": paper.is_historical_archive,
    })
    db.delete(paper)
    db.commit()
    get_storage_provider().delete_file(file_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
