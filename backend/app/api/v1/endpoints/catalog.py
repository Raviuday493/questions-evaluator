from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import parse_uuid
from app.core.security import SYLLABUS_ROLES, get_current_user
from app.db.session import get_db
from app.models.entities import Course, Department, SyllabusUnit, User, UserRole
from app.schemas import CourseOut, DepartmentOut, SyllabusIn, SyllabusUnitOut
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    """Public: needed by the registration form before the user has a session."""
    return db.scalars(select(Department).order_by(Department.name)).all()


@router.get("/courses", response_model=List[CourseOut])
def list_courses(
    department_code: Optional[str] = Query(None, max_length=50),
    search: Optional[str] = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Course).join(Department).options(joinedload(Course.department))
    if department_code:
        query = query.where(Department.code == department_code)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(or_(func.lower(Course.code).like(pattern), func.lower(Course.title).like(pattern)))
    return db.scalars(query.order_by(Course.code).limit(limit)).all()


def _get_course(db: Session, course_id: str) -> Course:
    course = db.get(Course, parse_uuid(course_id, "Course"))
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.get("/courses/{course_id}/syllabus", response_model=List[SyllabusUnitOut])
def get_syllabus(course_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_course(db, course_id).syllabus_units


@router.put("/courses/{course_id}/syllabus", response_model=List[SyllabusUnitOut])
def replace_syllabus(
    course_id: str,
    payload: SyllabusIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace a course's syllabus units. Existing analyses keep their unit tags until re-analysed."""
    course = _get_course(db, course_id)
    if current_user.role not in SYLLABUS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only department heads and administrators can edit syllabi")
    if current_user.role == UserRole.DEPT_HEAD and course.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit syllabi in your department")

    course.syllabus_units.clear()
    db.flush()
    for unit in payload.units:
        course.syllabus_units.append(SyllabusUnit(
            unit_number=unit.unit_number,
            title=unit.title.strip(),
            target_weightage_percent=unit.target_weightage_percent,
            keywords=[k.strip().lower() for k in unit.keywords if k.strip()],
        ))
    db.commit()
    AuditService.log_request(db, request, "SYLLABUS_UPDATE", course.id, actor_id=current_user.id)
    db.refresh(course)
    return course.syllabus_units
