"""Structured historical question and solution archive."""

import hashlib
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.admin.common import Page, like_pattern, paginate
from app.core.admin_security import AdminContext, require_permission
from app.db.session import get_db
from app.models.entities import ArchiveQuestion, ArchiveSolution
from app.services.audit_service import AuditService

router = APIRouter(prefix="/archive", tags=["admin: historical archive"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 500


class ArchiveRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=20000)
    solutions: list[str] = Field(min_length=1, max_length=20)
    subject: Optional[str] = Field(default=None, max_length=255)
    topic: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(min_length=1, max_length=255)
    source_reference: Optional[str] = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


def normalize_text(value: str) -> str:
    """Normalize Unicode and line endings while retaining indentation and internal spacing."""
    import unicodedata

    value = unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    )
    return "\n".join(line.rstrip(" \t") for line in value.split("\n")).strip()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_json_constant(value: str):
    raise ValueError(f"Invalid JSON constant: {value}")


def _row(record: ArchiveQuestion) -> dict:
    return {
        "id": str(record.id),
        "question": record.question_text,
        "subject": record.subject,
        "topic": record.topic,
        "source": record.source,
        "source_reference": record.source_reference,
        "ingested_at": record.ingested_at.isoformat(),
        "content_hash": record.content_hash,
        "metadata": record.metadata_json,
        "solutions": [
            {"id": str(s.id), "text": s.solution_text, "content_hash": s.content_hash}
            for s in record.solutions
        ],
    }


@router.post("/imports")
async def import_archive(
    request: Request,
    ctx: AdminContext = Depends(require_permission("archive.import")),
    db: Session = Depends(get_db),
):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_IMPORT_BYTES):
        raise HTTPException(
            status_code=413, detail=f"Import exceeds {MAX_IMPORT_BYTES} byte limit"
        )
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_IMPORT_BYTES:
            raise HTTPException(
                status_code=413, detail=f"Import exceeds {MAX_IMPORT_BYTES} byte limit"
            )
    try:
        payload = json.loads(body, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise HTTPException(status_code=400, detail="Request body must be valid JSON")
    if not isinstance(payload, list):
        raise HTTPException(status_code=422, detail="Import body must be a JSON array")
    if len(payload) > MAX_RECORDS:
        raise HTTPException(
            status_code=422, detail=f"Import may contain at most {MAX_RECORDS} records"
        )

    valid = []
    errors = []
    for index, item in enumerate(payload, start=1):
        try:
            record = ArchiveRecord.model_validate(item)
            q = normalize_text(record.question)
            solutions = [normalize_text(s) for s in record.solutions]
            if not q or any(not s for s in solutions) or not record.source.strip():
                raise ValueError(
                    "question, source, and solutions must contain non-whitespace text"
                )
            valid.append((index, record, q, solutions))
        except (ValidationError, ValueError) as exc:
            message = (
                "; ".join(
                    f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                    for error in exc.errors(include_input=False)
                )
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            errors.append(
                {"record": index, "status": "failed", "error": message[:1000]}
            )

    results = []
    try:
        for index, record, normalized, solutions in valid:
            source = record.source.strip()
            qhash = digest(normalized)
            source_key = digest(
                "\0".join(
                    (
                        source.casefold(),
                        (record.source_reference or "").strip(),
                    )
                )
            )
            archived = db.scalar(
                select(ArchiveQuestion)
                .where(
                    ArchiveQuestion.content_hash == qhash,
                    ArchiveQuestion.source_key == source_key,
                )
                .options(selectinload(ArchiveQuestion.solutions))
            )
            created = archived is None
            if archived is None:
                archived = ArchiveQuestion(
                    question_text=normalized,
                    normalized_text=normalized,
                    content_hash=qhash,
                    subject=record.subject.strip() if record.subject else None,
                    topic=record.topic.strip() if record.topic else None,
                    source=source,
                    source_reference=record.source_reference.strip()
                    if record.source_reference
                    else None,
                    source_key=source_key,
                    ingested_by_id=ctx.id,
                    metadata_json=record.metadata,
                )
                db.add(archived)
                db.flush()
            known = {s.content_hash for s in archived.solutions}
            added = 0
            for solution in solutions:
                shash = digest(solution)
                if shash in known:
                    continue
                db.add(
                    ArchiveSolution(
                        question_id=archived.id,
                        solution_text=solution,
                        content_hash=shash,
                    )
                )
                known.add(shash)
                added += 1
            db.flush()
            results.append(
                {
                    "record": index,
                    "status": "created"
                    if created and added
                    else ("updated" if added else "skipped"),
                    "question_id": str(archived.id),
                    "solutions_added": added,
                }
            )
        db.flush()
        AuditService.record_admin(
            db,
            request,
            ctx.id,
            "ARCHIVE_IMPORT",
            "archive",
            uuid.uuid4(),
            {
                "records": len(payload),
                "created_or_updated": sum(r["status"] != "skipped" for r in results),
                "skipped": sum(r["status"] == "skipped" for r in results),
                "failed": len(errors),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "total": len(payload),
        "results": sorted(results + errors, key=lambda x: x["record"]),
    }


@router.get("")
def list_archive(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    subject: Optional[str] = Query(None, max_length=255),
    topic: Optional[str] = Query(None, max_length=255),
    source: Optional[str] = Query(None, max_length=255),
    _: AdminContext = Depends(require_permission("papers.view")),
    db: Session = Depends(get_db),
):
    query = select(ArchiveQuestion)
    if search:
        pattern = like_pattern(search)
        query = query.where(
            or_(
                func.lower(ArchiveQuestion.question_text).like(pattern, escape="\\"),
                func.lower(ArchiveQuestion.source).like(pattern, escape="\\"),
            )
        )
    for column, value in (
        (ArchiveQuestion.subject, subject),
        (ArchiveQuestion.topic, topic),
        (ArchiveQuestion.source, source),
    ):
        if value:
            query = query.where(column == value)
    query = query.options(selectinload(ArchiveQuestion.solutions))
    return paginate(
        db, query, page, [ArchiveQuestion.ingested_at.desc(), ArchiveQuestion.id], _row
    )


@router.get("/{archive_id}")
def get_archive_record(
    archive_id: str,
    _: AdminContext = Depends(require_permission("papers.view")),
    db: Session = Depends(get_db),
):
    try:
        identifier = uuid.UUID(archive_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Archive record not found")
    record = db.scalar(
        select(ArchiveQuestion)
        .where(ArchiveQuestion.id == identifier)
        .options(selectinload(ArchiveQuestion.solutions))
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Archive record not found")
    return _row(record)
