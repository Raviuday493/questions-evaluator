"""End-to-end paper analysis: extract -> parse -> classify -> embed -> match -> analyse -> report.

Runs either in-process (FastAPI BackgroundTasks) or inside a Celery worker; each stage commits its
status so the frontend's status polling sees live progress.
"""
import logging
import time
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, is_postgres
from app.models.entities import (
    ANALYZED_STATUSES,
    IN_PROGRESS_STATUSES,
    Course,
    NextPaperRecommendation,
    PaperStatus,
    QPIReport,
    Question,
    QuestionPaperDraft,
    SimilarityMatch,
    SyllabusUnit,
)
from app.services.analytics_service import (
    HistoricalCycle,
    MatchInfo,
    PaperAnalytics,
    QuestionInfo,
    UnitInfo,
    academic_year_start,
    term_label,
)
from app.services.classification import classify_blooms, classify_question_type, classify_unit
from app.services.document_parser import DocumentExtractionError, DocumentParserService
from app.services.embedding_provider import get_embedding_provider
from app.services.ocr_service import OCRService, OCRUnavailableError
from app.services.similarity_engine import HybridSimilarityEngine, LexicalIndex
from app.services.runtime_settings import get_runtime_settings
from app.services.storage_service import get_storage_provider

logger = logging.getLogger("qpi.pipeline")

MATCHES_PER_QUESTION = 3
VECTOR_CANDIDATES = 25


class PipelineError(Exception):
    """A user-facing processing failure (message is shown in the UI)."""


def paper_source_label(paper: QuestionPaperDraft) -> str:
    return f"{term_label(paper.academic_year, paper.term)} {paper.exam_type}"


def _set_progress(db: Session, paper: QuestionPaperDraft, status: PaperStatus, percent: int, step: str) -> None:
    paper.status = status
    paper.progress_percent = percent
    paper.current_step = step
    db.commit()


# --------------------------------------------------------------------------- extraction
def _extract_text(file_bytes: bytes, mime_type: str) -> str:
    if "pdf" in mime_type:
        text_content, needs_ocr = DocumentParserService.extract_text_from_pdf(file_bytes)
        if needs_ocr:
            try:
                text_content = OCRService.extract_text_with_ocr(file_bytes)
            except OCRUnavailableError as exc:
                raise PipelineError(
                    f"This PDF has no selectable text (it looks scanned) and OCR could not run: {exc} "
                    "Upload a text-based PDF or DOCX."
                ) from exc
        return text_content
    return DocumentParserService.extract_text_from_docx(file_bytes)


def _persist_questions(db: Session, paper: QuestionPaperDraft, units: Sequence[SyllabusUnit]) -> List[Question]:
    file_bytes = get_storage_provider().get_file(paper.file_path)
    try:
        raw_text = _extract_text(file_bytes, paper.file_mime_type)
    except DocumentExtractionError as exc:
        raise PipelineError(str(exc)) from exc

    parsed = DocumentParserService.parse_questions_from_text(raw_text)
    if not parsed:
        raise PipelineError(
            "No questions could be identified in this document. Number questions as '1.', 'Q1.' or "
            "'Question 1' and sub-parts as '(a)', '(b)'."
        )

    by_number: Dict[str, Question] = {}
    questions: List[Question] = []
    for position, pq in enumerate(parsed):
        parent = by_number.get(pq.parent_question_number) if pq.parent_question_number else None
        unit = classify_unit(pq.clean_text, units)
        q = Question(
            id=uuid.uuid4(),
            paper_id=paper.id,
            position=position,
            section_name=pq.section_name,
            question_number=pq.question_number[:20],
            parent_question_id=parent.id if parent else None,
            raw_text=pq.raw_text,
            clean_text=pq.clean_text,
            marks=pq.marks,
            question_type=classify_question_type(pq.raw_text, pq.marks),
            blooms_level=classify_blooms(pq.clean_text),
            unit_id=unit.id if unit else None,
        )
        by_number.setdefault(pq.question_number, q)
        questions.append(q)
    # Parents are listed before their sub-questions, but insert in two passes so FKs resolve on flush.
    db.add_all([q for q in questions if q.parent_question_id is None])
    db.flush()
    db.add_all([q for q in questions if q.parent_question_id is not None])
    db.commit()
    return questions


# --------------------------------------------------------------------------- matching
def _revision_ancestors(db: Session, paper: QuestionPaperDraft) -> set:
    ancestors, current = set(), paper.previous_paper_id
    while current and current not in ancestors:
        ancestors.add(current)
        current = db.scalar(select(QuestionPaperDraft.previous_paper_id).where(QuestionPaperDraft.id == current))
    return ancestors


def _historical_papers(
    db: Session, paper: QuestionPaperDraft, lookback_years: int = settings.SIMILARITY_LOOKBACK_YEARS
) -> Tuple[List[QuestionPaperDraft], str]:
    """Authorised archive for this paper: same course first, falling back to the department (spec EC-003)."""
    excluded = _revision_ancestors(db, paper) | {paper.id}
    base = (
        select(QuestionPaperDraft)
        .where(
            QuestionPaperDraft.id.notin_(excluded),
            QuestionPaperDraft.status.in_(ANALYZED_STATUSES),
            or_(QuestionPaperDraft.is_historical_archive.is_(True), QuestionPaperDraft.status == PaperStatus.APPROVED),
        )
    )
    start = academic_year_start(paper.academic_year)

    def within_window(p: QuestionPaperDraft) -> bool:
        p_start = academic_year_start(p.academic_year)
        return start is None or p_start is None or p_start >= start - lookback_years

    course_papers = [p for p in db.scalars(base.where(QuestionPaperDraft.course_id == paper.course_id)) if within_window(p)]
    if course_papers:
        return course_papers, "COURSE"
    dept_course_ids = select(Course.id).where(Course.department_id == paper.course.department_id)
    dept_papers = [p for p in db.scalars(base.where(QuestionPaperDraft.course_id.in_(dept_course_ids))) if within_window(p)]
    if dept_papers:
        return dept_papers, "DEPARTMENT"
    return [], "NONE"


def _ensure_embeddings(db: Session, questions: Sequence[Question]) -> None:
    """Embed questions lacking a vector from the active model (also re-embeds after a provider switch)."""
    provider = get_embedding_provider()
    stale = [q for q in questions if q.embedding is None or q.embedding_model != provider.model_id]
    if not stale:
        return
    vectors = provider.generate_embeddings_batch([q.clean_text for q in stale])
    for q, vec in zip(stale, vectors):
        q.embedding = vec
        q.embedding_model = provider.model_id
    db.commit()


def _vector_candidates(db: Session, embedding: List[float], paper_ids: List[str], model_id: str) -> List[str]:
    """Top-K nearest historical questions via the pgvector HNSW index."""
    vec_literal = "[" + ",".join(f"{v:.7f}" for v in embedding) + "]"
    rows = db.execute(
        text(
            "SELECT id FROM questions WHERE paper_id = ANY(CAST(:paper_ids AS uuid[])) "
            "AND embedding_model = :model AND embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k"
        ),
        {"paper_ids": paper_ids, "model": model_id, "vec": vec_literal, "k": VECTOR_CANDIDATES},
    )
    return [str(r[0]) for r in rows]


def _match_questions(
    db: Session,
    draft_questions: Sequence[Question],
    historical: Sequence[QuestionPaperDraft],
    engine: Optional[HybridSimilarityEngine] = None,
) -> Tuple[Dict[uuid.UUID, List[SimilarityMatch]], int]:
    hist_questions = list(db.scalars(select(Question).where(Question.paper_id.in_([p.id for p in historical])))) if historical else []
    if not hist_questions:
        return {}, 0
    _ensure_embeddings(db, hist_questions)

    provider = get_embedding_provider()
    engine = engine or HybridSimilarityEngine()
    lexical_index = LexicalIndex(q.clean_text for q in hist_questions)
    pool = {
        str(q.id): {"id": q.id, "clean_text": q.clean_text, "embedding": q.embedding}
        for q in hist_questions
        if q.embedding is not None
    }
    use_pgvector = is_postgres()
    paper_ids = [str(p.id) for p in historical]
    if not use_pgvector:
        pool_ids = list(pool)
        pool_matrix = np.asarray([pool[i]["embedding"] for i in pool_ids], dtype=np.float32)
        norms = np.linalg.norm(pool_matrix, axis=1)
        norms[norms == 0] = 1.0

    matches: Dict[uuid.UUID, List[SimilarityMatch]] = {}
    for dq in draft_questions:
        if dq.embedding is None:
            continue
        if use_pgvector:
            candidate_ids = _vector_candidates(db, dq.embedding, paper_ids, provider.model_id)
        else:
            vec = np.asarray(dq.embedding, dtype=np.float32)
            sims = (pool_matrix @ vec) / (norms * (np.linalg.norm(vec) or 1.0))
            candidate_ids = [pool_ids[i] for i in np.argsort(-sims)[:VECTOR_CANDIDATES]]
        candidates = [pool[c] for c in candidate_ids if c in pool]
        results = engine.find_matches_for_question(dq.clean_text, dq.embedding, candidates, lexical_index)
        rows = [
            SimilarityMatch(
                draft_question_id=dq.id,
                historical_question_id=uuid.UUID(r.historical_question_id),
                semantic_score=r.semantic_score,
                lexical_score=r.lexical_score,
                composite_score=r.composite_score,
                match_tier=r.match_tier,
            )
            for r in results[:MATCHES_PER_QUESTION]
        ]
        if rows:
            db.add_all(rows)
            matches[dq.id] = rows
    db.commit()
    return matches, len(hist_questions)


# --------------------------------------------------------------------------- analytics & report
def _history_cycles(db: Session, paper: QuestionPaperDraft) -> List[HistoricalCycle]:
    """Units examined per historical cycle of *this course* (used for saturation and 'last covered')."""
    rows = db.execute(
        select(QuestionPaperDraft.academic_year, QuestionPaperDraft.term, Question.unit_id)
        .join(Question, Question.paper_id == QuestionPaperDraft.id)
        .where(
            QuestionPaperDraft.course_id == paper.course_id,
            QuestionPaperDraft.id != paper.id,
            QuestionPaperDraft.status.in_(ANALYZED_STATUSES),
            or_(QuestionPaperDraft.is_historical_archive.is_(True), QuestionPaperDraft.status == PaperStatus.APPROVED),
        )
    ).all()
    cycles: Dict[tuple, HistoricalCycle] = {}
    for year, term, unit_id in rows:
        cycle = cycles.setdefault((year, term), HistoricalCycle(year, term, set()))
        if unit_id:
            cycle.unit_ids.add(str(unit_id))
    return list(cycles.values())


def build_analytics(
    db: Session, paper: QuestionPaperDraft, questions: Sequence[Question], matches: Dict[uuid.UUID, List[SimilarityMatch]]
) -> PaperAnalytics:
    hist_ids = {m.historical_question_id for rows in matches.values() for m in rows}
    hist_lookup = {
        q.id: q for q in db.scalars(select(Question).where(Question.id.in_(hist_ids)))
    } if hist_ids else {}
    infos = []
    for q in questions:
        best = matches.get(q.id, [None])[0]
        match_info = None
        if best is not None:
            src = hist_lookup.get(best.historical_question_id)
            match_info = MatchInfo(
                tier=best.match_tier,
                composite_score=float(best.composite_score),
                source_label=paper_source_label(src.paper) if src else "archived",
                source_question_number=src.question_number if src else "?",
            )
        infos.append(QuestionInfo(
            id=str(q.id),
            number=q.question_number,
            text=q.clean_text,
            marks=q.marks or 0,
            parent_id=str(q.parent_question_id) if q.parent_question_id else None,
            unit_id=str(q.unit_id) if q.unit_id else None,
            blooms=q.blooms_level,
            qtype=q.question_type,
            best_match=match_info,
        ))
    units = [
        UnitInfo(str(u.id), u.unit_number, u.title, float(u.target_weightage_percent))
        for u in paper.course.syllabus_units
    ]
    return PaperAnalytics(infos, units, _history_cycles(db, paper))


def _write_report(
    db: Session,
    paper: QuestionPaperDraft,
    analytics: PaperAnalytics,
    scan: dict,
    elapsed: float,
) -> QPIReport:
    report = QPIReport(
        paper_id=paper.id,
        originality_score=analytics.originality_score(),
        total_questions=len(analytics.questions),
        matched_questions_count=len(analytics.matched_questions()),
        unit_coverage_json=analytics.unit_coverage(),
        blooms_distribution_json=analytics.blooms_distribution(),
        question_type_json=analytics.question_types(),
        overused_topics_json={
            "topics": analytics.overused_topics(paper.academic_year),
            "conceptual_gaps": analytics.conceptual_gaps(),
        },
        scan_metadata_json={**scan, "severity_breakdown": analytics.severity_breakdown()},
        processing_seconds=round(elapsed, 2),
    )
    db.add(report)
    db.flush()
    for priority, rec in enumerate(analytics.recommendations(paper.academic_year), start=1):
        db.add(NextPaperRecommendation(
            report_id=report.id,
            priority=priority,
            category=rec.category,
            target_question_id=uuid.UUID(rec.target_question_id) if rec.target_question_id else None,
            action_text=rec.action_text,
            rationale=rec.rationale,
        ))
    return report


def _reset_previous_results(db: Session, paper: QuestionPaperDraft) -> None:
    db.execute(delete(QPIReport).where(QPIReport.paper_id == paper.id))
    db.execute(delete(Question).where(Question.paper_id == paper.id))
    db.commit()
    db.expire(paper)


# --------------------------------------------------------------------------- entry points
def process_paper(paper_id: str) -> None:
    """Analyse one queued paper. Safe to call from a background thread or a Celery worker."""
    db = SessionLocal()
    try:
        paper = db.get(QuestionPaperDraft, uuid.UUID(str(paper_id)))
        if paper is None:
            logger.warning("process_paper: paper %s no longer exists", paper_id)
            return
        if paper.status != PaperStatus.QUEUED:
            logger.info("process_paper: paper %s is %s, skipping", paper_id, paper.status.value)
            return

        started = time.perf_counter()
        _reset_previous_results(db, paper)
        paper.error_message = None
        _set_progress(db, paper, PaperStatus.PARSING, 10, "Parsing layout & extracting questions...")
        units = list(paper.course.syllabus_units)
        questions = _persist_questions(db, paper, units)
        logger.info("Extracted %d questions for paper_id=%s", len(questions), paper_id)

        _set_progress(db, paper, PaperStatus.EMBEDDING, 40, "Generating vector embeddings...")
        _ensure_embeddings(db, questions)

        _set_progress(db, paper, PaperStatus.MATCHING, 65, "Scanning historical archive...")
        runtime = get_runtime_settings(db)
        engine = HybridSimilarityEngine(
            exact_threshold=runtime.exact_match_threshold,
            paraphrase_threshold=runtime.paraphrase_match_threshold,
            conceptual_threshold=runtime.conceptual_match_threshold,
            alpha=runtime.semantic_weight,
        )
        historical, scope = _historical_papers(db, paper, runtime.similarity_lookback_years)
        matches, hist_question_count = _match_questions(db, questions, historical, engine)

        _set_progress(db, paper, PaperStatus.MATCHING, 85, "Computing insights & recommendations...")
        years = sorted(y for p in historical if (y := academic_year_start(p.academic_year)) is not None)
        scan = {
            "scope": scope,
            "historical_papers_searched": len(historical),
            "historical_questions_searched": hist_question_count,
            "archive_year_range": f"{years[0]}-{years[-1] + 1}" if years else None,
            "embedding_model": get_embedding_provider().model_id,
            "thresholds": {
                "exact": runtime.exact_match_threshold,
                "paraphrase": runtime.paraphrase_match_threshold,
                "conceptual": runtime.conceptual_match_threshold,
            },
        }
        analytics = build_analytics(db, paper, questions, matches)
        _write_report(db, paper, analytics, scan, time.perf_counter() - started)
        _set_progress(db, paper, PaperStatus.COMPLETED, 100, "Analysis complete")
        logger.info("Paper processing completed for paper_id=%s in %.1fs", paper_id, time.perf_counter() - started)
    except PipelineError as exc:
        db.rollback()
        _mark_failed(db, paper_id, str(exc))
    except Exception:
        logger.exception("Paper processing failed for paper_id=%s", paper_id)
        db.rollback()
        _mark_failed(db, paper_id, "An unexpected error occurred while analysing this paper. Please retry.")
    finally:
        db.close()


def _mark_failed(db: Session, paper_id: str, message: str) -> None:
    paper = db.get(QuestionPaperDraft, uuid.UUID(str(paper_id)))
    if paper is not None:
        paper.status = PaperStatus.FAILED
        paper.error_message = message
        paper.current_step = "Analysis failed"
        db.commit()


def recover_interrupted_jobs() -> int:
    """Fail jobs left mid-flight by a server restart (in-process mode only) so users can retry them."""
    with SessionLocal() as db:
        stuck = list(db.scalars(
            select(QuestionPaperDraft).where(QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES))
        ))
        for paper in stuck:
            paper.status = PaperStatus.FAILED
            paper.current_step = "Analysis interrupted"
            paper.error_message = "Processing was interrupted by a server restart. Please retry the analysis."
        db.commit()
        return len(stuck)


def dispatch_processing(paper_id: str, background_tasks=None) -> None:
    """Queue a paper for analysis on the configured task backend."""
    if settings.TASK_QUEUE == "celery":
        from app.tasks.paper_tasks import process_paper_task

        process_paper_task.delay(str(paper_id))
    elif background_tasks is not None:
        background_tasks.add_task(process_paper, str(paper_id))
    else:
        process_paper(str(paper_id))
