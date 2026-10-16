from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import can_approve_paper, can_manage_paper, can_view_paper, parse_uuid
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.entities import (
    Course,
    QPIReport,
    Question,
    QuestionPaperDraft,
    SimilarityMatch,
    SyllabusUnit,
    User,
)
from app.services.audit_service import AuditService
from app.services.paper_pipeline import paper_source_label

router = APIRouter()


def _get_visible_report(db: Session, user: User, report_id: str) -> QPIReport:
    report = db.scalar(
        select(QPIReport)
        .options(
            joinedload(QPIReport.paper).joinedload(QuestionPaperDraft.course).joinedload(Course.department),
            joinedload(QPIReport.paper).joinedload(QuestionPaperDraft.uploader),
            selectinload(QPIReport.recommendations),
        )
        .where(QPIReport.id == parse_uuid(report_id, "Report"))
    )
    if report is None or not can_view_paper(user, report.paper):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _paper_block(paper: QuestionPaperDraft, user: User) -> dict:
    course = paper.course
    return {
        "id": str(paper.id),
        "course_code": course.code,
        "course_title": course.title,
        "department": course.department.name if course.department else None,
        "academic_year": paper.academic_year,
        "term": paper.term,
        "exam_type": paper.exam_type,
        "total_marks": paper.total_marks,
        "original_filename": paper.original_filename,
        "status": paper.status.value,
        "is_historical_archive": paper.is_historical_archive,
        "uploader_name": paper.uploader.full_name if paper.uploader else None,
        "uploaded_at": paper.created_at.isoformat(),
        "approved_at": paper.approved_at.isoformat() if paper.approved_at else None,
        "previous_paper_id": str(paper.previous_paper_id) if paper.previous_paper_id else None,
        "can_approve": can_approve_paper(user, paper),
        "can_manage": can_manage_paper(user, paper),
    }


def _previous_report(db: Session, user: User, paper: QuestionPaperDraft):
    if not paper.previous_paper_id:
        return None
    prev = db.scalar(
        select(QuestionPaperDraft)
        .options(joinedload(QuestionPaperDraft.report), joinedload(QuestionPaperDraft.course))
        .where(QuestionPaperDraft.id == paper.previous_paper_id)
    )
    if prev is None or prev.report is None or not can_view_paper(user, prev):
        return None
    return {
        "paper_id": str(prev.id),
        "report_id": str(prev.report.id),
        "originality_score": float(prev.report.originality_score),
    }


@router.get("/{id}")
def get_report(id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _get_visible_report(db, current_user, id)
    paper = report.paper

    questions: List[Question] = list(db.scalars(
        select(Question).options(joinedload(Question.unit)).where(Question.paper_id == paper.id).order_by(Question.position)
    ))
    match_rows = db.scalars(
        select(SimilarityMatch)
        .options(
            joinedload(SimilarityMatch.historical_question)
            .joinedload(Question.paper)
            .joinedload(QuestionPaperDraft.course)
        )
        .where(SimilarityMatch.draft_question_id.in_([q.id for q in questions]))
        .order_by(SimilarityMatch.composite_score.desc())
    ).all() if questions else []
    matches_by_question: Dict = {}
    for m in match_rows:
        matches_by_question.setdefault(m.draft_question_id, []).append(m)

    def match_payload(m: SimilarityMatch) -> dict:
        hq = m.historical_question
        hp = hq.paper
        return {
            "match_tier": m.match_tier.value,
            "composite_score": float(m.composite_score),
            "semantic_score": float(m.semantic_score),
            "lexical_score": float(m.lexical_score),
            "source_paper": paper_source_label(hp),
            "source": {
                "paper_id": str(hp.id),
                "course_code": hp.course.code,
                "academic_year": hp.academic_year,
                "term": hp.term,
                "exam_type": hp.exam_type,
                "question_number": hq.question_number,
                "text": hq.clean_text,
            },
        }

    question_payloads, matched_questions = [], []
    for q in questions:
        q_matches = [match_payload(m) for m in matches_by_question.get(q.id, [])]
        best = q_matches[0] if q_matches else None
        question_payloads.append({
            "id": str(q.id),
            "question_number": q.question_number,
            "section_name": q.section_name,
            "text": q.clean_text,
            "marks": q.marks,
            "question_type": q.question_type.value if q.question_type else None,
            "blooms_level": q.blooms_level.value if q.blooms_level else None,
            "unit": {"unit_number": q.unit.unit_number, "title": q.unit.title} if q.unit else None,
            "is_sub_question": q.parent_question_id is not None,
            "match_tier": best["match_tier"] if best else None,
            "composite_score": best["composite_score"] if best else None,
        })
        if best:
            matched_questions.append({
                "question_id": str(q.id),
                "question_number": q.question_number,
                "draft_text": q.clean_text,
                "marks": q.marks,
                **{k: best[k] for k in ("match_tier", "composite_score", "semantic_score", "lexical_score", "source_paper", "source")},
                "other_matches": q_matches[1:],
            })

    scan = report.scan_metadata_json or {}
    AuditService.log_request(db, request, "REPORT_VIEW", report.id, actor_id=current_user.id)
    return {
        "report_id": str(report.id),
        "paper_id": str(paper.id),
        "paper": _paper_block(paper, current_user),
        "originality_score": float(report.originality_score),
        "total_questions": report.total_questions,
        "matched_questions_count": report.matched_questions_count,
        "severity_breakdown": scan.get("severity_breakdown", {}),
        "scan": {k: v for k, v in scan.items() if k != "severity_breakdown"},
        "processing_seconds": report.processing_seconds,
        "generated_at": report.generated_at.isoformat(),
        "previous_report": _previous_report(db, current_user, paper),
        "matched_questions": matched_questions,
        "questions": question_payloads,
    }


@router.get("/{id}/insights")
def get_insights(id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _get_visible_report(db, current_user, id)
    paper = report.paper
    has_syllabus = db.scalar(select(SyllabusUnit.id).where(SyllabusUnit.course_id == paper.course_id).limit(1)) is not None
    topics = report.overused_topics_json or {}
    targets = {}
    if any(r.target_question_id for r in report.recommendations):
        ids = [r.target_question_id for r in report.recommendations if r.target_question_id]
        targets = {q.id: q.question_number for q in db.scalars(select(Question).where(Question.id.in_(ids)))}
    return {
        "report_id": str(report.id),
        "paper": _paper_block(paper, current_user),
        "draft_freshness_score": float(report.originality_score),
        "has_syllabus": has_syllabus,
        "unit_coverage": report.unit_coverage_json,
        "conceptual_gaps": topics.get("conceptual_gaps", []),
        "blooms_distribution": report.blooms_distribution_json,
        "question_types": report.question_type_json,
        "overused_topics": topics.get("topics", []),
        "recommendations": [
            {
                "priority": r.priority,
                "category": r.category.value,
                "action_text": r.action_text,
                "rationale": r.rationale,
                "target_question_number": targets.get(r.target_question_id),
            }
            for r in report.recommendations
        ],
        "scan": {k: v for k, v in (report.scan_metadata_json or {}).items() if k != "severity_breakdown"},
    }
