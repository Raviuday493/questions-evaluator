import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.entities import PaperStatus, UserRole

ALLOWED_TERMS = ("Fall", "Spring", "Summer")
ALLOWED_EXAM_TYPES = ("Final Examination", "Midterm Examination", "Quiz")
EXAM_TYPE_ALIASES = {"final": "Final Examination", "midterm": "Midterm Examination", "quiz": "Quiz"}
COURSE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\- ]{1,30}$")
ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})-(\d{4})$")


def normalize_course_code(value: str) -> str:
    code = re.sub(r"\s+", " ", (value or "").strip().upper())
    if not COURSE_CODE_RE.match(code):
        raise ValueError("Course code must be 2-31 characters of letters, digits, spaces or hyphens (e.g. PHY-201).")
    return code


def normalize_academic_year(value: str) -> str:
    m = ACADEMIC_YEAR_RE.match((value or "").strip())
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ValueError("Academic year must look like 2025-2026.")
    return m.group(0)


def normalize_term(value: str) -> str:
    for term in ALLOWED_TERMS:
        if (value or "").strip().lower() == term.lower():
            return term
    raise ValueError(f"Term must be one of: {', '.join(ALLOWED_TERMS)}.")


def normalize_exam_type(value: str) -> str:
    cleaned = (value or "").strip()
    for exam_type in ALLOWED_EXAM_TYPES:
        if cleaned.lower() == exam_type.lower():
            return exam_type
    if cleaned.lower() in EXAM_TYPE_ALIASES:
        return EXAM_TYPE_ALIASES[cleaned.lower()]
    raise ValueError(f"Exam type must be one of: {', '.join(ALLOWED_EXAM_TYPES)}.")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users
class DepartmentOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    department: Optional[DepartmentOut] = None
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    department_code: Optional[str] = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name is required.")
        return v

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes.")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------- courses / syllabus
class CourseOut(ORMModel):
    id: uuid.UUID
    code: str
    title: str
    department: DepartmentOut


class SyllabusUnitIn(BaseModel):
    unit_number: int = Field(ge=1, le=50)
    title: str = Field(min_length=1, max_length=255)
    target_weightage_percent: float = Field(ge=0, le=100)
    keywords: List[str] = Field(default_factory=list, max_length=100)


class SyllabusUnitOut(ORMModel):
    id: uuid.UUID
    unit_number: int
    title: str
    target_weightage_percent: float
    keywords: List[str]


class SyllabusIn(BaseModel):
    units: List[SyllabusUnitIn] = Field(max_length=50)

    @field_validator("units")
    @classmethod
    def _validate_units(cls, units: List[SyllabusUnitIn]) -> List[SyllabusUnitIn]:
        numbers = [u.unit_number for u in units]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Unit numbers must be unique.")
        total = sum(u.target_weightage_percent for u in units)
        if units and abs(total - 100) > 0.5:
            raise ValueError(f"Unit target weightages must sum to 100% (got {total:g}%).")
        return units


# ---------------------------------------------------------------- papers
class PaperSummary(BaseModel):
    id: uuid.UUID
    course_code: str
    course_title: str
    department: Optional[str]
    department_code: Optional[str]
    academic_year: str
    term: str
    exam_type: str
    total_marks: int
    original_filename: str
    status: PaperStatus
    progress_percent: int
    current_step: Optional[str]
    error_message: Optional[str]
    is_historical_archive: bool
    previous_paper_id: Optional[uuid.UUID]
    report_id: Optional[uuid.UUID]
    originality_score: Optional[float]
    matched_questions_count: Optional[int]
    uploader_name: str
    is_owner: bool
    created_at: datetime
    updated_at: datetime


class PaperList(BaseModel):
    items: List[PaperSummary]
    total: int
    page: int
    limit: int
    pages: int


class UploadAccepted(BaseModel):
    paper_id: uuid.UUID
    status: PaperStatus
    status_url: str


class PaperStatusOut(BaseModel):
    paper_id: uuid.UUID
    status: PaperStatus
    progress_percent: int
    current_step: Optional[str]
    error_message: Optional[str]
    report_id: Optional[uuid.UUID]


# ---------------------------------------------------------------- dashboard
class DashboardStats(BaseModel):
    total_analyzed: int
    analyzed_last_30_days: int
    analyzed_change_percent: Optional[float]
    avg_originality: Optional[float]
    in_progress: int
    failed: int
    approved: int
    total_matches: int


class GenericMessage(BaseModel):
    detail: str


JSONDict = Dict[str, Any]
