import logging
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("qpi.db")


def normalize_database_url(url: str) -> str:
    """The app uses a synchronous engine (shared by API and Celery worker); map async drivers."""
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    # Hosted providers hand out driver-less URLs; SQLAlchemy 2.1 would pick psycopg (v3), which isn't installed.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def _build_engine(url: str):
    url = normalize_database_url(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = _build_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"
