import hashlib
import io
import math
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import (
    can_approve_paper,
    can_manage_paper,
    get_visible_paper,
    paper_visibility_clause,
    parse_uuid,
)
from app.core.config import settings
from app.core.security import ARCHIVE_ROLES, get_current_user
from app.db.session import get_db
from app.models.entities import (
    Course,
    Department,
    PaperStatus,
    QPIReport,
    QuestionPaperDraft,
    User,
)
from app.schemas import (
    PaperList,
    PaperStatusOut,
    PaperSummary,
    UploadAccepted,
    normalize_academic_year,
    normalize_course_code,
    normalize_exam_type,
    normalize_term,
)
from app.services.audit_service import AuditService
from app.services.file_validation import FileValidationError, validate_upload
from app.services.paper_pipeline import dispatch_processing
from app.services.runtime_settings import get_runtime_settings
from app.services.storage_service import get_storage_provider

router = APIRouter()

SORT_COLUMNS = {
    "created_at": QuestionPaperDraft.created_at,
    "academic_year": QuestionPaperDraft.academic_year,
    "status": QuestionPaperDraft.status,
    "course_code": Course.code,
    "originality_score": QPIReport.originality_score,
}


def paper_summary(paper: QuestionPaperDraft, user: User) -> PaperSummary:
    report = paper.report
    return PaperSummary(
        id=paper.id,
        course_code=paper.course.code,
        course_title=paper.course.title,
        department=paper.course.department.name if paper.course.department else None,
        department_code=paper.course.department.code if paper.course.department else None,
        academic_year=paper.academic_year,
        term=paper.term,
        exam_type=paper.exam_type,
        total_marks=paper.total_marks,
        original_filename=paper.original_filename,
        status=paper.status,
        progress_percent=paper.progress_percent,
        current_step=paper.current_step,
        error_message=paper.error_message,
        is_historical_archive=paper.is_historical_archive,
        previous_paper_id=paper.previous_paper_id,
        report_id=report.id if report else None,
        originality_score=float(report.originality_score) if report else None,
        matched_questions_count=report.matched_questions_count if report else None,
        uploader_name=paper.uploader.full_name if paper.uploader else "Unknown",
        is_owner=paper.uploader_id == user.id,
        created_at=paper.created_at,
        updated_at=paper.updated_at,
    )


def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read the upload in chunks, aborting as soon as it exceeds the size limit."""
    chunks, size = [], 0
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed limit of {limit // (1024 * 1024)}MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validation_error(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _resolve_course(
    db: Session, user: User, course_id: Optional[str], course_code: Optional[str], department_code: Optional[str], academic_year: str
) -> Course:
    if course_id:
        course = db.get(Course, parse_uuid(course_id, "Course"))
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        return course
    if not course_code:
        raise _validation_error("Course code is required.")
    try:
        code = normalize_course_code(course_code)
    except ValueError as exc:
        raise _validation_error(str(exc))

    if department_code:
        department = db.scalar(select(Department).where(Department.code == department_code))
        if department is None:
            raise _validation_error("Unknown department.")
    elif user.department_id:
        department = db.get(Department, user.department_id)
    else:
        raise _validation_error("Please select a department.")

    course = db.scalar(select(Course).where(Course.department_id == department.id, Course.code == code))
    if course is None:
        course = Course(department_id=department.id, code=code, title=code, academic_year=academic_year)
        db.add(course)
        db.flush()
    return course


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=UploadAccepted)
def upload_paper(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    academic_year: str = Form(...),
    term: str = Form(...),
    exam_type: str = Form(...),
    total_marks: int = Form(100),
    course_code: Optional[str] = Form(None),
    department_code: Optional[str] = Form(None),
    course_id: Optional[str] = Form(None),
    previous_paper_id: Optional[str] = Form(None),
    is_historical_archive: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        academic_year = normalize_academic_year(academic_year)
        term = normalize_term(term)
        exam_type = normalize_exam_type(exam_type)
    except ValueError as exc:
        raise _validation_error(str(exc))
    if not 1 <= total_marks <= 1000:
        raise _validation_error("Total marks must be between 1 and 1000.")
    if is_historical_archive and current_user.role not in ARCHIVE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only archival administrators can add papers to the historical archive")

    runtime = get_runtime_settings(db)
    if not runtime.uploads_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Uploads are temporarily paused for maintenance. Please try again later.",
        )
    content = _read_limited(file, runtime.max_upload_bytes)
    try:
        validated = validate_upload(file.filename or "", content, max_bytes=runtime.max_upload_bytes)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    course = _resolve_course(db, current_user, course_id, course_code, department_code, academic_year)

    previous = None
    if previous_paper_id:
        previous = get_visible_paper(db, current_user, previous_paper_id)
        if not can_manage_paper(current_user, previous):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only revise your own papers")
        if previous.course_id != course.id:
            raise _validation_error("A revised draft must belong to the same course as the original paper.")

    file_hash = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(
        select(QuestionPaperDraft).where(
            QuestionPaperDraft.uploader_id == current_user.id,
            QuestionPaperDraft.course_id == course.id,
            QuestionPaperDraft.file_hash == file_hash,
            QuestionPaperDraft.status != PaperStatus.FAILED,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This exact file was already uploaded for {course.code} ({duplicate.term} {duplicate.academic_year}). Open it from the dashboard instead.",
        )

    paper_id = uuid.uuid4()
    department = db.get(Department, course.department_id)
    rel_path = f"{department.code}/{course.code.replace(' ', '_')}/{academic_year}/{paper_id}{validated.extension}"
    storage = get_storage_provider()
    storage.save_file(io.BytesIO(content), rel_path)

    paper = QuestionPaperDraft(
        id=paper_id,
        uploader_id=current_user.id,
        course_id=course.id,
        previous_paper_id=previous.id if previous else None,
        academic_year=academic_year,
        term=term,
        exam_type=exam_type,
        total_marks=total_marks,
        original_filename=validated.safe_name,
        file_path=rel_path,
        file_mime_type=validated.mime_type,
        file_size_bytes=len(content),
        file_hash=file_hash,
        is_historical_archive=is_historical_archive,
        status=PaperStatus.QUEUED,
        progress_percent=0,
        current_step="Queued for analysis",
    )
    db.add(paper)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_file(rel_path)
        raise

    AuditService.log_request(
        db, request, "PAPER_UPLOAD", paper.id, actor_id=current_user.id,
        details={"course_code": course.code, "filename": validated.safe_name, "revision_of": str(previous.id) if previous else None},
    )
    dispatch_processing(str(paper.id), background_tasks)
    return UploadAccepted(
        paper_id=paper.id,
        status=PaperStatus.QUEUED,
        status_url=f"{settings.API_V1_STR}/papers/{paper.id}/status",
    )


@router.get("", response_model=PaperList)
def list_papers(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[str] = Query(None, alias="status", description="Comma-separated statuses"),
    course_code: Optional[str] = Query(None, max_length=50),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if sort not in SORT_COLUMNS:
        raise _validation_error(f"sort must be one of: {', '.join(SORT_COLUMNS)}")

    query = (
        select(QuestionPaperDraft)
        .join(Course, Course.id == QuestionPaperDraft.course_id)
        .outerjoin(QPIReport, QPIReport.paper_id == QuestionPaperDraft.id)
    )
    visibility = paper_visibility_clause(current_user)
    if visibility is not None:
        query = query.where(visibility)
    if status_filter:
        try:
            statuses = [PaperStatus(s.strip().upper()) for s in status_filter.split(",") if s.strip()]
        except ValueError:
            raise _validation_error(f"status must be one of: {', '.join(s.value for s in PaperStatus)}")
        query = query.where(QuestionPaperDraft.status.in_(statuses))
    if course_code:
        query = query.where(Course.code == course_code.strip().upper())
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(or_(
            func.lower(Course.code).like(pattern),
            func.lower(Course.title).like(pattern),
            func.lower(QuestionPaperDraft.original_filename).like(pattern),
            func.lower(QuestionPaperDraft.exam_type).like(pattern),
            func.lower(QuestionPaperDraft.academic_year).like(pattern),
        ))

    total = db.scalar(select(func.count()).select_from(query.with_only_columns(QuestionPaperDraft.id).subquery()))
    column = SORT_COLUMNS[sort]
    ordering = column.asc() if order == "asc" else column.desc()
    if sort == "originality_score":
        ordering = ordering.nulls_last()
    rows = db.scalars(
        query.options(
            joinedload(QuestionPaperDraft.course).joinedload(Course.department),
            joinedload(QuestionPaperDraft.report),
            joinedload(QuestionPaperDraft.uploader),
        )
        .order_by(ordering, QuestionPaperDraft.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).unique()
    return PaperList(
        items=[paper_summary(p, current_user) for p in rows],
        total=total,
        page=page,
        limit=limit,
        pages=max(1, math.ceil(total / limit)),
    )


@router.get("/{id}", response_model=PaperSummary)
def get_paper(id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return paper_summary(get_visible_paper(db, current_user, id), current_user)


@router.get("/{id}/status", response_model=PaperStatusOut)
def get_paper_status(id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = get_visible_paper(db, current_user, id)
    return PaperStatusOut(
        paper_id=paper.id,
        status=paper.status,
        progress_percent=paper.progress_percent,
        current_step=paper.current_step,
        error_message=paper.error_message,
        report_id=paper.report.id if paper.report else None,
    )


@router.get("/{id}/file")
def download_paper_file(id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = get_visible_paper(db, current_user, id)
    try:
        content = get_storage_provider().get_file(paper.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The original file is no longer available")
    AuditService.log_request(db, request, "PAPER_DOWNLOAD", paper.id, actor_id=current_user.id)
    return Response(
        content=content,
        media_type=paper.file_mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(paper.original_filename)}"},
    )


@router.post("/{id}/reanalyze", status_code=status.HTTP_202_ACCEPTED, response_model=PaperStatusOut)
def reanalyze_paper(
    id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper = get_visible_paper(db, current_user, id)
    if not can_manage_paper(current_user, paper):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only re-analyse your own papers")
    # Re-analysing an archived paper would drop the match records other reports point to.
    if paper.status == PaperStatus.FAILED or (paper.status == PaperStatus.COMPLETED and not paper.is_historical_archive):
        paper.status = PaperStatus.QUEUED
        paper.progress_percent = 0
        paper.current_step = "Queued for analysis"
        paper.error_message = None
        db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A paper with status {paper.status.value} cannot be re-analysed",
        )
    AuditService.log_request(db, request, "PAPER_REANALYZE", paper.id, actor_id=current_user.id)
    dispatch_processing(str(paper.id), background_tasks)
    return PaperStatusOut(
        paper_id=paper.id, status=paper.status, progress_percent=0,
        current_step=paper.current_step, error_message=None, report_id=None,
    )


@router.post("/{id}/approve", response_model=PaperSummary)
def approve_paper(id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = get_visible_paper(db, current_user, id)
    if not can_approve_paper(current_user, paper):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to approve this paper")
    if paper.status != PaperStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only completed analyses can be approved")
    paper.status = PaperStatus.APPROVED
    paper.approved_at = datetime.now(timezone.utc)
    paper.approved_by_id = current_user.id
    paper.current_step = "Approved for exam archive"
    db.commit()
    AuditService.log_request(db, request, "PAPER_APPROVE", paper.id, actor_id=current_user.id)
    return paper_summary(paper, current_user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = get_visible_paper(db, current_user, id)
    if not can_manage_paper(current_user, paper):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own papers")
    if paper.status == PaperStatus.APPROVED and current_user.role not in ARCHIVE_ROLES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approved papers are part of the exam archive and cannot be deleted")
    if paper.status in (PaperStatus.PARSING, PaperStatus.EMBEDDING, PaperStatus.MATCHING):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This paper is currently being analysed; try again when it finishes")
    file_path, paper_uuid = paper.file_path, paper.id
    db.delete(paper)
    db.commit()
    get_storage_provider().delete_file(file_path)
    AuditService.log_request(db, request, "PAPER_DELETE", paper_uuid, actor_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
