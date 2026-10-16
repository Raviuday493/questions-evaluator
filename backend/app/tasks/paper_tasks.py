import logging

from app.core.celery_app import celery_app
from app.services.paper_pipeline import process_paper

logger = logging.getLogger("qpi.tasks")


@celery_app.task(name="process_paper_task")
def process_paper_task(paper_id: str) -> str:
    """Celery entry point; progress and results are persisted by the pipeline itself."""
    logger.info("Starting async processing for paper_id=%s", paper_id)
    process_paper(paper_id)
    return paper_id
