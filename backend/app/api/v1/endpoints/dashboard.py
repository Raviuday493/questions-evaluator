from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import paper_visibility_clause
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.entities import ANALYZED_STATUSES, IN_PROGRESS_STATUSES, PaperStatus, QPIReport, QuestionPaperDraft, User
from app.schemas import DashboardStats

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """KPI tiles for the faculty dashboard, scoped to the papers the user can see.

    Historical archive ingests are excluded so the numbers reflect draft papers under preparation.
    """
    visibility = paper_visibility_clause(current_user)

    def scoped(query):
        query = query.where(QuestionPaperDraft.is_historical_archive.is_(False))
        return query.where(visibility) if visibility is not None else query

    def count(*conditions) -> int:
        return db.scalar(scoped(select(func.count(QuestionPaperDraft.id)).where(*conditions))) or 0

    analyzed = QuestionPaperDraft.status.in_(ANALYZED_STATUSES)
    now = datetime.now(timezone.utc)
    last_30 = count(analyzed, QuestionPaperDraft.created_at >= now - timedelta(days=30))
    prev_30 = count(
        analyzed,
        QuestionPaperDraft.created_at >= now - timedelta(days=60),
        QuestionPaperDraft.created_at < now - timedelta(days=30),
    )
    change = round(100.0 * (last_30 - prev_30) / prev_30, 1) if prev_30 else None

    report_scope = scoped(
        select(func.avg(QPIReport.originality_score), func.coalesce(func.sum(QPIReport.matched_questions_count), 0))
        .join(QuestionPaperDraft, QuestionPaperDraft.id == QPIReport.paper_id)
        .where(analyzed)
    )
    avg_originality, total_matches = db.execute(report_scope).one()

    return DashboardStats(
        total_analyzed=count(analyzed),
        analyzed_last_30_days=last_30,
        analyzed_change_percent=change,
        avg_originality=round(float(avg_originality), 1) if avg_originality is not None else None,
        in_progress=count(QuestionPaperDraft.status.in_(IN_PROGRESS_STATUSES)),
        failed=count(QuestionPaperDraft.status == PaperStatus.FAILED),
        approved=count(QuestionPaperDraft.status == PaperStatus.APPROVED),
        total_matches=int(total_matches or 0),
    )
