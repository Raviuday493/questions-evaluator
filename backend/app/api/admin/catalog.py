"""Departments, courses and syllabus units."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.admin.common import (
    Page,
    conflict,
    invalid,
    iso,
    like_pattern,
    not_found,
    paginate,
    parse_id,
    parse_optional_uuid,
)
from app.core.admin_security import AdminContext, require_permission
from app.db.session import get_db
from app.models.entities import Course, Department, QPIReport, QuestionPaperDraft, SyllabusUnit, User
from app.schemas import SyllabusIn, normalize_academic_year, normalize_course_code
from app.schemas.admin import CourseIn, CourseUpdateIn, DepartmentIn, DepartmentUpdateIn
from app.services.audit_service import AuditService

router = APIRouter()


# ------------------------------------------------------------------ departments
def _dept_counts(db: Session) -> dict:
    users = dict(db.execute(select(User.department_id, func.count(User.id)).group_by(User.department_id)).all())
    courses = dict(db.execute(select(Course.department_id, func.count(Course.id)).group_by(Course.department_id)).all())
    papers = dict(db.execute(
        select(Course.department_id, func.count(QuestionPaperDraft.id))
        .join(QuestionPaperDraft, QuestionPaperDraft.course_id == Course.id)
        .group_by(Course.department_id)
    ).all())
    return {"users": users, "courses": courses, "papers": papers}


def department_row(d: Department, counts: Optional[dict] = None) -> dict:
    counts = counts or {"users": {}, "courses": {}, "papers": {}}
    return {
        "id": str(d.id),
        "code": d.code,
        "name": d.name,
        "created_at": iso(d.created_at),
        "user_count": counts["users"].get(d.id, 0),
        "course_count": counts["courses"].get(d.id, 0),
        "paper_count": counts["papers"].get(d.id, 0),
    }


@router.get("/departments")
def list_departments(
    search: Optional[str] = Query(None, max_length=100),
    _: AdminContext = Depends(require_permission("catalog.view")),
    db: Session = Depends(get_db),
):
    query = select(Department)
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(func.lower(Department.code).like(pattern, escape="\\"),
                                func.lower(Department.name).like(pattern, escape="\\")))
    counts = _dept_counts(db)
    return [department_row(d, counts) for d in db.scalars(query.order_by(Department.name))]


def _get_department(db: Session, department_id: str) -> Department:
    dept = db.get(Department, parse_id(department_id, "Department"))
    if dept is None:
        raise not_found("Department")
    return dept


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentIn, request: Request,
                      ctx: AdminContext = Depends(require_permission("catalog.edit")), db: Session = Depends(get_db)):
    if db.scalar(select(Department.id).where(Department.code == payload.code)):
        raise conflict(f"Department code {payload.code} is already in use")
    dept = Department(code=payload.code, name=payload.name)
    db.add(dept)
    db.flush()
    AuditService.record_admin(db, request, ctx.id, "DEPARTMENT_CREATE", "department", dept.id, payload.model_dump())
    db.commit()
    return department_row(dept, _dept_counts(db))


@router.patch("/departments/{department_id}")
def update_department(department_id: str, payload: DepartmentUpdateIn, request: Request,
                      ctx: AdminContext = Depends(require_permission("catalog.edit")), db: Session = Depends(get_db)):
    dept = _get_department(db, department_id)
    changes = {}
    if payload.code is not None and payload.code != dept.code:
        if db.scalar(select(Department.id).where(Department.code == payload.code, Department.id != dept.id)):
            raise conflict(f"Department code {payload.code} is already in use")
        # Stored file paths embed the old code; they stay valid because paths are looked up, not rebuilt.
        changes["code"] = [dept.code, payload.code]
        dept.code = payload.code
    if payload.name is not None and payload.name != dept.name:
        changes["name"] = [dept.name, payload.name]
        dept.name = payload.name
    if changes:
        AuditService.record_admin(db, request, ctx.id, "DEPARTMENT_UPDATE", "department", dept.id, {"changes": changes})
        db.commit()
    return department_row(dept, _dept_counts(db))


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: str, request: Request,
                      ctx: AdminContext = Depends(require_permission("catalog.delete")), db: Session = Depends(get_db)):
    dept = _get_department(db, department_id)
    courses = db.scalar(select(func.count(Course.id)).where(Course.department_id == dept.id)) or 0
    users = db.scalar(select(func.count(User.id)).where(User.department_id == dept.id)) or 0
    if courses or users:
        raise conflict(
            f"This department still has {courses} course(s) and {users} user(s). Move or remove them first."
        )
    AuditService.record_admin(db, request, ctx.id, "DEPARTMENT_DELETE", "department", dept.id,
                              {"code": dept.code, "name": dept.name})
    db.delete(dept)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ courses
def course_row(c: Course, paper_count: int = 0, unit_count: Optional[int] = None) -> dict:
    return {
        "id": str(c.id),
        "code": c.code,
        "title": c.title,
        "academic_year": c.academic_year,
        "department": {"id": str(c.department.id), "code": c.department.code, "name": c.department.name} if c.department else None,
        "created_at": iso(c.created_at),
        "paper_count": paper_count,
        "unit_count": unit_count,
    }


def _course_counts(db: Session, ids) -> tuple:
    if not ids:
        return {}, {}
    papers = dict(db.execute(
        select(QuestionPaperDraft.course_id, func.count(QuestionPaperDraft.id))
        .where(QuestionPaperDraft.course_id.in_(ids)).group_by(QuestionPaperDraft.course_id)
    ).all())
    units = dict(db.execute(
        select(SyllabusUnit.course_id, func.count(SyllabusUnit.id))
        .where(SyllabusUnit.course_id.in_(ids)).group_by(SyllabusUnit.course_id)
    ).all())
    return papers, units


SORTS = {"code": Course.code, "title": Course.title, "created_at": Course.created_at, "academic_year": Course.academic_year}


@router.get("/courses")
def list_courses(
    page: Page = Depends(),
    search: Optional[str] = Query(None, max_length=100),
    department_id: Optional[str] = None,
    sort: str = "code",
    order: str = Query("asc", pattern="^(asc|desc)$"),
    _: AdminContext = Depends(require_permission("catalog.view")),
    db: Session = Depends(get_db),
):
    if sort not in SORTS:
        raise invalid(f"sort must be one of: {', '.join(SORTS)}")
    query = select(Course).options(joinedload(Course.department))
    if search:
        pattern = like_pattern(search)
        query = query.where(or_(func.lower(Course.code).like(pattern, escape="\\"),
                                func.lower(Course.title).like(pattern, escape="\\")))
    dept = parse_optional_uuid(department_id, "department_id")
    if dept:
        query = query.where(Course.department_id == dept)
    column = SORTS[sort]
    result = paginate(db, query, page, [column.asc() if order == "asc" else column.desc(), Course.id], lambda c: c)
    papers, units = _course_counts(db, [c.id for c in result["items"]])
    result["items"] = [course_row(c, papers.get(c.id, 0), units.get(c.id, 0)) for c in result["items"]]
    return result


def _get_course(db: Session, course_id: str) -> Course:
    course = db.scalar(select(Course).options(joinedload(Course.department)).where(Course.id == parse_id(course_id, "Course")))
    if course is None:
        raise not_found("Course")
    return course


def _normalize_course_fields(code: Optional[str], year: Optional[str]) -> tuple:
    try:
        return (normalize_course_code(code) if code is not None else None,
                normalize_academic_year(year) if year is not None else None)
    except ValueError as exc:
        raise invalid(str(exc))


def unit_row(u: SyllabusUnit) -> dict:
    return {"id": str(u.id), "unit_number": u.unit_number, "title": u.title,
            "target_weightage_percent": float(u.target_weightage_percent), "keywords": u.keywords or []}


@router.get("/courses/{course_id}")
def get_course(course_id: str, _: AdminContext = Depends(require_permission("catalog.view")), db: Session = Depends(get_db)):
    course = _get_course(db, course_id)
    papers, units = _course_counts(db, [course.id])
    stats = db.execute(
        select(func.count(QPIReport.id), func.avg(QPIReport.originality_score))
        .join(QuestionPaperDraft, QuestionPaperDraft.id == QPIReport.paper_id)
        .where(QuestionPaperDraft.course_id == course.id, QuestionPaperDraft.is_historical_archive.is_(False))
    ).one()
    archive = db.scalar(select(func.count(QuestionPaperDraft.id)).where(
        QuestionPaperDraft.course_id == course.id, QuestionPaperDraft.is_historical_archive.is_(True))) or 0
    return {
        **course_row(course, papers.get(course.id, 0), units.get(course.id, 0)),
        "syllabus": [unit_row(u) for u in course.syllabus_units],
        "stats": {
            "analyzed_drafts": stats[0] or 0,
            "avg_originality": round(float(stats[1]), 1) if stats[1] is not None else None,
            "archive_papers": archive,
        },
    }


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseIn, request: Request,
                  ctx: AdminContext = Depends(require_permission("catalog.edit")), db: Session = Depends(get_db)):
    code, year = _normalize_course_fields(payload.code, payload.academic_year)
    title = payload.title.strip()
    if len(title) < 2:
        raise invalid("Title must be at least 2 characters.")
    if db.get(Department, payload.department_id) is None:
        raise invalid("Unknown department")
    if db.scalar(select(Course.id).where(Course.department_id == payload.department_id, Course.code == code)):
        raise conflict(f"Course {code} already exists in this department")
    course = Course(department_id=payload.department_id, code=code, title=title, academic_year=year)
    db.add(course)
    db.flush()
    AuditService.record_admin(db, request, ctx.id, "COURSE_CREATE", "course", course.id, {"code": code, "title": title})
    db.commit()
    return course_row(_get_course(db, str(course.id)), 0, 0)


@router.patch("/courses/{course_id}")
def update_course(course_id: str, payload: CourseUpdateIn, request: Request,
                  ctx: AdminContext = Depends(require_permission("catalog.edit")), db: Session = Depends(get_db)):
    course = _get_course(db, course_id)
    code, year = _normalize_course_fields(payload.code, payload.academic_year)
    changes = {}
    target_dept = payload.department_id or course.department_id
    if payload.department_id and db.get(Department, payload.department_id) is None:
        raise invalid("Unknown department")
    target_code = code or course.code
    if (target_code, target_dept) != (course.code, course.department_id) and db.scalar(
        select(Course.id).where(Course.department_id == target_dept, Course.code == target_code, Course.id != course.id)
    ):
        raise conflict(f"Course {target_code} already exists in that department")
    if code and code != course.code:
        changes["code"] = [course.code, code]
        course.code = code
    if payload.department_id and payload.department_id != course.department_id:
        changes["department_id"] = [str(course.department_id), str(payload.department_id)]
        course.department_id = payload.department_id
    if payload.title is not None:
        title = payload.title.strip()
        if len(title) < 2:
            raise invalid("Title must be at least 2 characters.")
        if title != course.title:
            changes["title"] = [course.title, title]
            course.title = title
    if year and year != course.academic_year:
        changes["academic_year"] = [course.academic_year, year]
        course.academic_year = year
    if changes:
        AuditService.record_admin(db, request, ctx.id, "COURSE_UPDATE", "course", course.id, {"changes": changes})
        db.commit()
        db.expire(course)
    papers, units = _course_counts(db, [course.id])
    return course_row(_get_course(db, course_id), papers.get(course.id, 0), units.get(course.id, 0))


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: str, request: Request,
                  ctx: AdminContext = Depends(require_permission("catalog.delete")), db: Session = Depends(get_db)):
    course = _get_course(db, course_id)
    papers = db.scalar(select(func.count(QuestionPaperDraft.id)).where(QuestionPaperDraft.course_id == course.id)) or 0
    if papers:
        raise conflict(f"This course has {papers} paper(s). Delete or move them before deleting the course.")
    AuditService.record_admin(db, request, ctx.id, "COURSE_DELETE", "course", course.id, {"code": course.code, "title": course.title})
    db.delete(course)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/courses/{course_id}/syllabus")
def replace_syllabus(course_id: str, payload: SyllabusIn, request: Request,
                     ctx: AdminContext = Depends(require_permission("catalog.edit")), db: Session = Depends(get_db)):
    course = _get_course(db, course_id)
    before = len(course.syllabus_units)
    course.syllabus_units.clear()
    db.flush()
    for unit in payload.units:
        course.syllabus_units.append(SyllabusUnit(
            unit_number=unit.unit_number,
            title=unit.title.strip(),
            target_weightage_percent=unit.target_weightage_percent,
            keywords=[k.strip().lower() for k in unit.keywords if k.strip()],
        ))
    AuditService.record_admin(db, request, ctx.id, "SYLLABUS_UPDATE", "course", course.id,
                              {"units_before": before, "units_after": len(payload.units)})
    db.commit()
    db.refresh(course)
    return [unit_row(u) for u in course.syllabus_units]
