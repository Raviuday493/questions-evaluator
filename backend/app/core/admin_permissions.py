"""Admin-panel permission catalog and the built-in (system) roles.

Permissions are plain strings checked by the backend on every admin request; the admin frontend
only uses them to hide controls. `*` grants everything and is reserved for the Super Admin role.
"""
from typing import Dict, Iterable, List

WILDCARD = "*"
SUPER_ADMIN_ROLE = "super_admin"

# key -> (group, description)
PERMISSIONS: Dict[str, tuple] = {
    "dashboard.view": ("Dashboard", "View dashboard KPIs, charts and recent activity"),
    "users.view": ("Users", "View application users and their activity"),
    "users.create": ("Users", "Create application user accounts"),
    "users.edit": ("Users", "Edit user profiles, roles and departments; reset passwords"),
    "users.status": ("Users", "Activate / deactivate users and sign them out everywhere"),
    "users.delete": ("Users", "Delete users that own no papers"),
    "papers.view": ("Papers", "View question papers, questions and originality reports"),
    "papers.download": ("Papers", "Download original uploaded files"),
    "papers.manage": ("Papers", "Re-analyse, approve and fail stuck analyses"),
    "papers.delete": ("Papers", "Delete papers (including archived ones)"),
    "archive.import": ("Historical Archive", "Import authorized historical questions and solutions"),
    "catalog.view": ("Catalog", "View departments, courses and syllabi"),
    "catalog.edit": ("Catalog", "Create and edit departments, courses and syllabi"),
    "catalog.delete": ("Catalog", "Delete unused departments and courses"),
    "reports.view": ("Reports", "View analytics reports"),
    "reports.export": ("Reports", "Export data as CSV"),
    "audit.view": ("Audit", "View the audit log"),
    "settings.view": ("Settings", "View runtime settings"),
    "settings.edit": ("Settings", "Change runtime settings"),
    "system.view": ("System", "View system health and configuration"),
    "admins.view": ("Administrators", "View admin accounts and roles"),
    "admins.manage": ("Administrators", "Create, edit, deactivate and delete admin accounts"),
    "roles.manage": ("Administrators", "Create and edit custom admin roles"),
}

_VIEW_ONLY = [p for p in PERMISSIONS if p.endswith(".view")]

# key -> (name, description, permissions). Synced into admin_roles on startup and by the migration.
SYSTEM_ROLES: Dict[str, tuple] = {
    SUPER_ADMIN_ROLE: ("Super Admin", "Full access, including administrator and role management.", [WILDCARD]),
    "admin": (
        "Administrator",
        "Manages users, papers, catalog, reports and settings. Cannot manage administrators.",
        [p for p in PERMISSIONS if p not in ("admins.manage", "roles.manage")],
    ),
    "academic_manager": (
        "Academic Manager",
        "Curates the paper archive, courses and syllabi.",
        ["dashboard.view", "users.view", "papers.view", "papers.download", "papers.manage", "papers.delete", "archive.import",
         "catalog.view", "catalog.edit", "catalog.delete", "reports.view", "reports.export"],
    ),
    "support": (
        "Support",
        "Helps faculty with their accounts and stuck analyses.",
        ["dashboard.view", "users.view", "users.edit", "users.status", "papers.view", "papers.manage",
         "catalog.view", "audit.view"],
    ),
    "auditor": (
        "Auditor",
        "Read-only access to everything, plus exports.",
        _VIEW_ONLY + ["reports.export"],
    ),
}


def has_permission(granted: Iterable[str], permission: str) -> bool:
    granted = set(granted or ())
    return WILDCARD in granted or permission in granted


def effective_permissions(granted: Iterable[str]) -> List[str]:
    granted = set(granted or ())
    if WILDCARD in granted:
        return sorted(PERMISSIONS)
    return sorted(p for p in granted if p in PERMISSIONS)


def permission_catalog() -> List[dict]:
    return [{"key": k, "group": g, "description": d} for k, (g, d) in PERMISSIONS.items()]
