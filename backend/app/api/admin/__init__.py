"""Admin-panel API, mounted at /api/v1/admin. Every route except /auth/login requires an admin session."""
from fastapi import APIRouter

from app.api.admin import admins, analytics, audit, auth, catalog, papers, system, users

admin_router = APIRouter()
admin_router.include_router(auth.router, prefix="/auth", tags=["admin: auth"])
admin_router.include_router(analytics.router, tags=["admin: dashboard & reports"])
admin_router.include_router(users.router, prefix="/users", tags=["admin: users"])
admin_router.include_router(papers.router, prefix="/papers", tags=["admin: papers"])
admin_router.include_router(catalog.router, tags=["admin: catalog"])
admin_router.include_router(audit.router, prefix="/audit-logs", tags=["admin: audit"])
admin_router.include_router(admins.router, tags=["admin: administrators"])
admin_router.include_router(system.router, tags=["admin: system"])
