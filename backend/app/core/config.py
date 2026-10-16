from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Question Paper Intelligence API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(default="development", description="development or production")

    # Database (synchronous driver; an async '+asyncpg' URL is transparently mapped to psycopg2)
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://qpi:secret@localhost:5432/qpi_db",
        description="PostgreSQL connection string (sqlite:/// URLs are supported for tests)",
    )

    # Background processing: 'background' runs the pipeline in-process after the upload
    # response; 'celery' dispatches it to a Celery worker via Redis.
    TASK_QUEUE: str = Field(default="background", description="background or celery")

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # File Storage
    STORAGE_TYPE: str = Field(default="local", description="local (filesystem) or database (stored_files table)")
    LOCAL_STORAGE_DIR: str = str(BACKEND_DIR / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 25
    S3_BUCKET_NAME: str = "qpi-paper-uploads"
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"

    # Configurable Similarity Thresholds (Requirement: Must be configurable)
    EXACT_MATCH_THRESHOLD: float = Field(default=0.90, description="Threshold for Exact Repetition")
    PARAPHRASE_MATCH_THRESHOLD: float = Field(default=0.75, description="Threshold for Paraphrased Repetition")
    CONCEPTUAL_MATCH_THRESHOLD: float = Field(default=0.60, description="Threshold for Conceptual Repetition")
    SEMANTIC_WEIGHT: float = Field(default=0.70, description="Alpha weight of semantic vs lexical score")
    SIMILARITY_LOOKBACK_YEARS: int = Field(default=10, description="Historical archive window in academic years")

    # Embedding Configuration (Pluggable Abstraction)
    EMBEDDING_PROVIDER: str = Field(
        default="sentence_transformers",
        description="sentence_transformers, hashing, or mock (falls back to hashing if sentence-transformers is not installed)",
    )
    EMBEDDING_MODEL_NAME: str = "all-mpnet-base-v2"
    EMBEDDING_DIMENSION: int = 768

    # Security
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool | None = None  # defaults to True in production
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        description="Comma-separated list of allowed browser origins (main site and admin panel)",
    )

    # Admin panel sessions (separate from application-user JWTs)
    ADMIN_SESSION_IDLE_MINUTES: int = Field(default=60, ge=5, description="Sign admins out after this much inactivity")
    ADMIN_SESSION_MAX_HOURS: int = Field(default=12, ge=1, description="Absolute admin session lifetime")
    ADMIN_MAX_FAILED_LOGINS: int = Field(default=5, ge=1, description="Failed admin logins before a temporary lock")
    ADMIN_LOCKOUT_MINUTES: int = Field(default=15, ge=1)
    STUCK_JOB_MINUTES: int = Field(default=30, ge=1, description="In-progress analyses older than this are flagged as stuck")

    # Google ADK Gemini Key
    GEMINI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.is_production and self.JWT_SECRET_KEY == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set to a strong secret when ENVIRONMENT=production")
        if "*" in self.cors_origins_list:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed with credentialed requests")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
