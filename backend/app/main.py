import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qpi")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _sync_admin_roles()
    if settings.TASK_QUEUE != "celery":
        from app.services.paper_pipeline import recover_interrupted_jobs

        try:
            recovered = recover_interrupted_jobs()
            if recovered:
                logger.warning("Marked %d interrupted analysis job(s) as FAILED", recovered)
        except Exception:
            logger.exception("Could not check for interrupted jobs (is the database migrated?)")
        _warm_embedding_model()
    yield


def _sync_admin_roles() -> None:
    from app.core.admin_security import sync_system_roles
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            sync_system_roles(db)
    except Exception:
        logger.exception("Could not sync built-in admin roles (is the database migrated?)")


def _warm_embedding_model() -> None:
    """Load the embedding model in the background so the first upload doesn't pay for it."""
    import threading

    from app.services.embedding_provider import get_embedding_provider

    def _load():
        try:
            get_embedding_provider().generate_embedding("warm-up")
        except Exception:
            logger.exception("Embedding model warm-up failed")

    threading.Thread(target=_load, name="embedding-warmup", daemon=True).start()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    lifespan=lifespan,
)

# Browsers normally reach the API through the Next.js proxy (same origin); CORS covers direct access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Request"],
)

from app.api.admin import admin_router  # noqa: E402
from app.api.v1.api import api_router  # noqa: E402

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin")


@app.get("/health")
def health_check():
    from app.db.session import engine

    database = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    return {
        "status": "healthy" if database == "ok" else "degraded",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": database,
        "task_queue": settings.TASK_QUEUE,
        "similarity_thresholds": {
            "exact": settings.EXACT_MATCH_THRESHOLD,
            "paraphrase": settings.PARAPHRASE_MATCH_THRESHOLD,
            "conceptual": settings.CONCEPTUAL_MATCH_THRESHOLD,
        }
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path", "form")]
        msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        errors.append({"field": ".".join(loc), "message": msg})
    summary = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
    return JSONResponse(
        status_code=422,
        content={"detail": summary or "Invalid request", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )
