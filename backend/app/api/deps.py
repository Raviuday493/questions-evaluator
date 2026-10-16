"""Shared RBAC helpers (FR-024): faculty see their own papers, department heads see their department,
archival/system admins see everything. Invisible papers are reported as 404 to avoid ID enumeration."""
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Course, QuestionPaperDraft, User, UserRole

ADMIN_ROLES = (UserRole.ARCHIVAL_ADMIN, UserRole.SYSTEM_ADMIN)


def paper_visibility_clause(user: User):
    """SQL filter restricting QuestionPaperDraft rows to those the user may see."""
    if user.role in ADMIN_ROLES:
        return None
    if user.role == UserRole.DEPT_HEAD and user.department_id is not None:
        dept_courses = select(Course.id).where(Course.department_id == user.department_id)
        return or_(QuestionPaperDraft.uploader_id == user.id, QuestionPaperDraft.course_id.in_(dept_courses))
    return QuestionPaperDraft.uploader_id == user.id


def can_view_paper(user: User, paper: QuestionPaperDraft) -> bool:
    if user.role in ADMIN_ROLES or paper.uploader_id == user.id:
        return True
    return (
        user.role == UserRole.DEPT_HEAD
        and user.department_id is not None
        and paper.course.department_id == user.department_id
    )


def can_manage_paper(user: User, paper: QuestionPaperDraft) -> bool:
    """Delete / re-analyse: the uploader or an admin."""
    return user.role in ADMIN_ROLES or paper.uploader_id == user.id


def can_approve_paper(user: User, paper: QuestionPaperDraft) -> bool:
    return can_manage_paper(user, paper) or (
        user.role == UserRole.DEPT_HEAD
        and user.department_id is not None
        and paper.course.department_id == user.department_id
    )


def parse_uuid(value: str, label: str = "Resource") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")


def get_visible_paper(db: Session, user: User, paper_id: str) -> QuestionPaperDraft:
    paper: Optional[QuestionPaperDraft] = db.scalar(
        select(QuestionPaperDraft)
        .options(
            joinedload(QuestionPaperDraft.course).joinedload(Course.department),
            joinedload(QuestionPaperDraft.report),
            joinedload(QuestionPaperDraft.uploader),
        )
        .where(QuestionPaperDraft.id == parse_uuid(paper_id, "Paper"))
    )
    if paper is None or not can_view_paper(user, paper):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    return paper
