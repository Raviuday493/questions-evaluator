import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import declarative_base, relationship

from app.core.config import settings
from app.db.types import EmbeddingVector, PortableJSON

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_cls):
    # VARCHAR + CHECK constraint (matches data-model.md) instead of native PG enum types.
    return SQLEnum(enum_cls, native_enum=False, length=50, validate_strings=True)


class UserRole(str, Enum):
    FACULTY = "FACULTY"
    DEPT_HEAD = "DEPT_HEAD"
    ARCHIVAL_ADMIN = "ARCHIVAL_ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class PaperStatus(str, Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    EMBEDDING = "EMBEDDING"
    MATCHING = "MATCHING"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    FAILED = "FAILED"


IN_PROGRESS_STATUSES = (PaperStatus.QUEUED, PaperStatus.PARSING, PaperStatus.EMBEDDING, PaperStatus.MATCHING)
ANALYZED_STATUSES = (PaperStatus.COMPLETED, PaperStatus.APPROVED)


class QuestionType(str, Enum):
    MCQ = "MCQ"
    SHORT_ANSWER = "SHORT_ANSWER"
    LONG_ESSAY = "LONG_ESSAY"
    NUMERICAL = "NUMERICAL"
    DERIVATION = "DERIVATION"


class BloomsLevel(str, Enum):
    REMEMBER = "REMEMBER"
    UNDERSTAND = "UNDERSTAND"
    APPLY = "APPLY"
    ANALYZE = "ANALYZE"
    EVALUATE = "EVALUATE"
    CREATE = "CREATE"


class MatchTier(str, Enum):
    EXACT = "EXACT"
    PARAPHRASED = "PARAPHRASED"
    CONCEPTUAL = "CONCEPTUAL"


class RecommendationCategory(str, Enum):
    REPETITION_SWAP = "REPETITION_SWAP"
    UNIT_REBALANCE = "UNIT_REBALANCE"
    BLOOMS_ELEVATION = "BLOOMS_ELEVATION"
    FORMAT_DIVERSIFICATION = "FORMAT_DIVERSIFICATION"


class Department(Base):
    __tablename__ = "departments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    users = relationship("User", back_populates="department")
    courses = relationship("Course", back_populates="department")


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(_enum(UserRole), nullable=False, default=UserRole.FACULTY)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    # Tokens issued before this instant are rejected (admin "sign out everywhere" / password reset).
    sessions_invalidated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    department = relationship("Department", back_populates="users")
    drafts = relationship("QuestionPaperDraft", back_populates="uploader", foreign_keys="QuestionPaperDraft.uploader_id")


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("department_id", "code", name="uq_courses_department_code"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    academic_year = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    department = relationship("Department", back_populates="courses")
    syllabus_units = relationship(
        "SyllabusUnit", back_populates="course", cascade="all, delete-orphan", order_by="SyllabusUnit.unit_number"
    )
    drafts = relationship("QuestionPaperDraft", back_populates="course")


class SyllabusUnit(Base):
    __tablename__ = "syllabus_units"
    __table_args__ = (UniqueConstraint("course_id", "unit_number", name="uq_syllabus_units_course_number"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    course_id = Column(Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    unit_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    target_weightage_percent = Column(Numeric(5, 2), nullable=False)
    keywords = Column(PortableJSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    course = relationship("Course", back_populates="syllabus_units")
    questions = relationship("Question", back_populates="unit")


class QuestionPaperDraft(Base):
    __tablename__ = "question_paper_drafts"
    __table_args__ = (
        Index("ix_papers_uploader_created", "uploader_id", "created_at"),
        Index("ix_papers_course_year", "course_id", "academic_year"),
        Index("ix_papers_status_created", "status", "created_at"),
        Index("ix_papers_created_at", "created_at"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    uploader_id = Column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    course_id = Column(Uuid, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False)
    previous_paper_id = Column(Uuid, ForeignKey("question_paper_drafts.id", ondelete="SET NULL"), nullable=True)
    academic_year = Column(String(20), nullable=False)
    term = Column(String(50), nullable=False)
    exam_type = Column(String(50), nullable=False)
    total_marks = Column(Integer, nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    file_hash = Column(String(64), nullable=False, index=True)
    is_historical_archive = Column(Boolean, nullable=False, default=False)
    status = Column(_enum(PaperStatus), nullable=False, default=PaperStatus.QUEUED)
    progress_percent = Column(Integer, nullable=False, default=0)
    current_step = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    uploader = relationship("User", back_populates="drafts", foreign_keys=[uploader_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    course = relationship("Course", back_populates="drafts")
    previous_paper = relationship("QuestionPaperDraft", remote_side=[id], foreign_keys=[previous_paper_id])
    questions = relationship(
        "Question", back_populates="paper", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Question.position",
    )
    report = relationship("QPIReport", back_populates="paper", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id = Column(Uuid, ForeignKey("question_paper_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    section_name = Column(String(100), nullable=True)
    question_number = Column(String(20), nullable=False)
    parent_question_id = Column(Uuid, ForeignKey("questions.id", ondelete="CASCADE"), nullable=True)
    raw_text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=False)
    marks = Column(Integer, nullable=False, default=0)
    question_type = Column(_enum(QuestionType), nullable=True)
    blooms_level = Column(_enum(BloomsLevel), nullable=True)
    unit_id = Column(Uuid, ForeignKey("syllabus_units.id", ondelete="SET NULL"), nullable=True)
    embedding = Column(EmbeddingVector(settings.EMBEDDING_DIMENSION), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    paper = relationship("QuestionPaperDraft", back_populates="questions")
    unit = relationship("SyllabusUnit", back_populates="questions")
    parent = relationship("Question", remote_side=[id])


class SimilarityMatch(Base):
    __tablename__ = "similarity_matches"
    __table_args__ = (UniqueConstraint("draft_question_id", "historical_question_id", name="uq_similarity_pair"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    draft_question_id = Column(Uuid, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    historical_question_id = Column(Uuid, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    semantic_score = Column(Numeric(5, 4), nullable=False)
    lexical_score = Column(Numeric(5, 4), nullable=False)
    composite_score = Column(Numeric(5, 4), nullable=False)
    match_tier = Column(_enum(MatchTier), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    draft_question = relationship("Question", foreign_keys=[draft_question_id])
    historical_question = relationship("Question", foreign_keys=[historical_question_id])


class QPIReport(Base):
    __tablename__ = "qpi_reports"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id = Column(Uuid, ForeignKey("question_paper_drafts.id", ondelete="CASCADE"), unique=True, nullable=False)
    originality_score = Column(Numeric(5, 2), nullable=False)
    total_questions = Column(Integer, nullable=False)
    matched_questions_count = Column(Integer, nullable=False)
    unit_coverage_json = Column(PortableJSON, nullable=False, default=dict)
    blooms_distribution_json = Column(PortableJSON, nullable=False, default=dict)
    question_type_json = Column(PortableJSON, nullable=False, default=dict)
    overused_topics_json = Column(PortableJSON, nullable=False, default=dict)
    scan_metadata_json = Column(PortableJSON, nullable=False, default=dict)
    processing_seconds = Column(Float, nullable=True)
    generated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    paper = relationship("QuestionPaperDraft", back_populates="report")
    recommendations = relationship(
        "NextPaperRecommendation", back_populates="report", cascade="all, delete-orphan", passive_deletes=True,
        order_by="NextPaperRecommendation.priority",
    )


class NextPaperRecommendation(Base):
    __tablename__ = "next_paper_recommendations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id = Column(Uuid, ForeignKey("qpi_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    priority = Column(Integer, nullable=False)
    category = Column(_enum(RecommendationCategory), nullable=False)
    target_question_id = Column(Uuid, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    action_text = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    report = relationship("QPIReport", back_populates="recommendations")


class AuditLog(Base):
    """Append-only activity trail. `actor_id` is an application user, `admin_id` an admin-panel account."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_actor_timestamp", "actor_id", "created_at"),
        Index("ix_audit_logs_admin_created", "admin_id", "created_at"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource_id", "resource_id"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_id = Column(Uuid, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    resource_id = Column(Uuid, nullable=False)
    details = Column(PortableJSON, nullable=False, default=dict)
    ip_hash = Column(String(64), nullable=False)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    actor = relationship("User", foreign_keys=[actor_id])
    admin = relationship("AdminUser", foreign_keys=[admin_id])


class StoredFile(Base):
    """File contents kept in the database (STORAGE_TYPE=database) for hosts without persistent disks."""

    __tablename__ = "stored_files"

    path = Column(String(512), primary_key=True)
    content = Column(LargeBinary, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# --------------------------------------------------------------------------- admin panel
class AdminRole(Base):
    """A named permission set for admin-panel accounts. System roles are defined in code and read-only."""

    __tablename__ = "admin_roles"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    permissions = Column(PortableJSON, nullable=False, default=list)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    admins = relationship("AdminUser", back_populates="role")


class AdminUser(Base):
    """Admin-panel account, deliberately separate from application `users`."""

    __tablename__ = "admin_users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Uuid, ForeignKey("admin_roles.id", ondelete="RESTRICT"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Uuid, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    role = relationship("AdminRole", back_populates="admins")
    sessions = relationship("AdminSession", back_populates="admin", cascade="all, delete-orphan", passive_deletes=True)


class AdminSession(Base):
    """Server-side admin session; the browser only holds an opaque token whose SHA-256 is stored here."""

    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_admin_created", "admin_id", "created_at"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    admin_id = Column(Uuid, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_hash = Column(String(64), nullable=False)
    user_agent = Column(String(255), nullable=True)

    admin = relationship("AdminUser", back_populates="sessions")


class AppSetting(Base):
    """Runtime configuration editable from the admin panel (overrides the environment defaults)."""

    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(PortableJSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    updated_by_id = Column(Uuid, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
