"""Admin-panel API: authentication, RBAC, management endpoints, runtime settings and the audit trail."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.admin_security import sync_system_roles, utcnow
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import AdminRole, AdminSession, AdminUser, AuditLog, Course, Department, PaperStatus, QuestionPaperDraft, User
from tests.helpers import PASSWORD, make_client, pdf_bytes, upload

ADMIN_PASSWORD = "AdminPassword123"
ADMIN = "/api/v1/admin"
DRAFT = [
    "1. A projectile is launched at 30 degrees with velocity 20 m/s. Calculate its range. (10 marks)",
    "2. State Newton's second law of motion and explain it with an example. (10 marks)",
]


def create_admin(email: str, role_key: str = "super_admin", password: str = ADMIN_PASSWORD) -> str:
    with SessionLocal() as db:
        sync_system_roles(db)
        role = db.scalar(select(AdminRole).where(AdminRole.key == role_key))
        admin = AdminUser(email=email, full_name=email.split("@")[0].title(), password_hash=hash_password(password), role_id=role.id)
        db.add(admin)
        db.commit()
        return str(admin.id)


def admin_client(email: str, password: str = ADMIN_PASSWORD) -> TestClient:
    c = TestClient(app, headers={"X-Admin-Request": "1"})
    r = c.post(f"{ADMIN}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def superadmin():
    create_admin("root@qpi-admin.edu")
    return admin_client("root@qpi-admin.edu")


def _user_id(email: str) -> str:
    with SessionLocal() as db:
        return str(db.scalar(select(User.id).where(User.email == email)))


def _actions() -> list:
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog.action).where(AuditLog.admin_id.is_not(None))))


# ------------------------------------------------------------------ authentication
def test_login_logout_me_and_invalid_credentials(client):
    create_admin("root@qpi-admin.edu")
    c = TestClient(app, headers={"X-Admin-Request": "1"})
    assert c.get(f"{ADMIN}/auth/me").status_code == 401
    assert c.post(f"{ADMIN}/auth/login", json={"email": "root@qpi-admin.edu", "password": "wrong-pass1"}).status_code == 401
    assert c.post(f"{ADMIN}/auth/login", json={"email": "nobody@qpi-admin.edu", "password": "x"}).status_code == 401
    r = c.post(f"{ADMIN}/auth/login", json={"email": "ROOT@qpi-admin.edu", "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["is_super_admin"] and "admins.manage" in body["permissions"] and "password_hash" not in body
    assert "qpi_admin_session" in r.cookies
    assert c.get(f"{ADMIN}/auth/me").json()["email"] == "root@qpi-admin.edu"
    assert c.post(f"{ADMIN}/auth/logout").status_code == 204
    assert c.get(f"{ADMIN}/auth/me").status_code == 401
    assert {"ADMIN_LOGIN", "ADMIN_LOGIN_FAILED", "ADMIN_LOGOUT"} <= set(_actions())


def test_csrf_header_is_required_for_cookie_requests(client):
    create_admin("root@qpi-admin.edu")
    bare = TestClient(app)
    assert bare.post(f"{ADMIN}/auth/login", json={"email": "root@qpi-admin.edu", "password": ADMIN_PASSWORD}).status_code == 403
    c = admin_client("root@qpi-admin.edu")
    token = c.cookies.get("qpi_admin_session")
    bare.cookies.set("qpi_admin_session", token)
    assert bare.get(f"{ADMIN}/auth/me").status_code == 200  # safe methods are fine
    assert bare.post(f"{ADMIN}/departments", json={"code": "BIO", "name": "Biology"}).status_code == 403
    # Bearer tokens carry no ambient authority, so no CSRF header is needed.
    api = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    assert api.post(f"{ADMIN}/departments", json={"code": "BIO", "name": "Biology"}).status_code == 201


def test_user_and_admin_credentials_are_not_interchangeable(client, faculty_client):
    assert faculty_client.get(f"{ADMIN}/users").status_code == 401
    token = client.post("/api/v1/auth/token", data={"username": "archivist@test.edu", "password": PASSWORD}).json()["access_token"]
    assert TestClient(app).get(f"{ADMIN}/users", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    create_admin("root@qpi-admin.edu")
    admin = admin_client("root@qpi-admin.edu")
    assert TestClient(app, cookies=dict(admin.cookies)).get("/api/v1/auth/me").status_code == 401


def test_account_lockout_after_repeated_failures(client):
    create_admin("root@qpi-admin.edu")
    c = TestClient(app, headers={"X-Admin-Request": "1"})
    for _ in range(5):
        assert c.post(f"{ADMIN}/auth/login", json={"email": "root@qpi-admin.edu", "password": "bad-password1"}).status_code == 401
    r = c.post(f"{ADMIN}/auth/login", json={"email": "root@qpi-admin.edu", "password": ADMIN_PASSWORD})
    assert r.status_code == 429


def test_expired_and_revoked_sessions_are_rejected(superadmin):
    with SessionLocal() as db:
        s = db.scalars(select(AdminSession)).one()
        s.last_seen_at = utcnow() - timedelta(hours=3)
        db.commit()
    assert superadmin.get(f"{ADMIN}/auth/me").status_code == 401
    c = admin_client("root@qpi-admin.edu")
    sessions = c.get(f"{ADMIN}/auth/sessions").json()
    current = next(s for s in sessions if s["is_current"])
    assert c.delete(f"{ADMIN}/auth/sessions/{current['id']}").status_code == 204
    assert c.get(f"{ADMIN}/auth/me").status_code == 401


def test_change_password(superadmin):
    r = superadmin.post(f"{ADMIN}/auth/change-password", json={"current_password": "nope", "new_password": "BrandNewPass99"})
    assert r.status_code == 422
    r = superadmin.post(f"{ADMIN}/auth/change-password", json={"current_password": ADMIN_PASSWORD, "new_password": "short1"})
    assert r.status_code == 422
    r = superadmin.post(f"{ADMIN}/auth/change-password", json={"current_password": ADMIN_PASSWORD, "new_password": "BrandNewPass99"})
    assert r.status_code == 204
    admin_client("root@qpi-admin.edu", "BrandNewPass99")


# ------------------------------------------------------------------ RBAC
def test_permissions_are_enforced_by_the_backend(client):
    create_admin("support@qpi-admin.edu", "support")
    c = admin_client("support@qpi-admin.edu")
    me = c.get(f"{ADMIN}/auth/me").json()
    assert "settings.edit" not in me["permissions"]
    assert c.get(f"{ADMIN}/users").status_code == 200
    assert c.get(f"{ADMIN}/settings").status_code == 403
    assert c.put(f"{ADMIN}/settings", json={"values": {"uploads_enabled": False}}).status_code == 403
    assert c.get(f"{ADMIN}/admins").status_code == 403
    assert c.delete(f"{ADMIN}/users/{_user_id('other@test.edu')}").status_code == 403
    assert c.get(f"{ADMIN}/users/export").status_code == 403  # needs reports.export
    # Frontend-supplied role hints are ignored.
    assert c.get(f"{ADMIN}/admins", headers={"X-Role": "super_admin"}, params={"isAdmin": "true"}).status_code == 403


def test_privilege_escalation_is_blocked(superadmin):
    roles = {r["key"]: r["id"] for r in superadmin.get(f"{ADMIN}/roles").json()}
    r = superadmin.post(f"{ADMIN}/roles", json={"name": "Team Lead", "permissions": ["admins.view", "admins.manage", "users.view"]})
    assert r.status_code == 201
    lead_role = r.json()["id"]
    r = superadmin.post(f"{ADMIN}/admins", json={"email": "lead@qpi-admin.edu", "full_name": "Team Lead",
                                                   "password": ADMIN_PASSWORD, "role_id": lead_role})
    assert r.status_code == 201
    lead = admin_client("lead@qpi-admin.edu")
    for key in ("super_admin", "admin"):
        r = lead.post(f"{ADMIN}/admins", json={"email": f"{key}@x-corp.edu", "full_name": "Sneaky", "password": ADMIN_PASSWORD,
                                                "role_id": roles[key]})
        assert r.status_code == 403, key
    root_id = superadmin.get(f"{ADMIN}/auth/me").json()["id"]
    assert lead.patch(f"{ADMIN}/admins/{root_id}", json={"is_active": False}).status_code == 403
    assert lead.patch(f"{ADMIN}/admins/{lead.get(f'{ADMIN}/auth/me').json()['id']}", json={"role_id": roles["super_admin"]}).status_code == 403
    assert lead.post(f"{ADMIN}/roles", json={"name": "x", "permissions": []}).status_code == 403  # lacks roles.manage
    # System roles are immutable.
    assert superadmin.patch(f"{ADMIN}/roles/{roles['support']}", json={"permissions": ["*"]}).status_code in (403, 422)
    assert superadmin.delete(f"{ADMIN}/roles/{roles['support']}").status_code == 403
    # A role in use cannot be deleted.
    assert superadmin.delete(f"{ADMIN}/roles/{lead_role}").status_code == 409


def test_last_super_admin_and_self_protection(superadmin):
    me = superadmin.get(f"{ADMIN}/auth/me").json()
    roles = {r["key"]: r["id"] for r in superadmin.get(f"{ADMIN}/roles").json()}
    assert superadmin.patch(f"{ADMIN}/admins/{me['id']}", json={"is_active": False}).status_code == 403
    assert superadmin.patch(f"{ADMIN}/admins/{me['id']}", json={"role_id": roles["support"]}).status_code == 403
    assert superadmin.delete(f"{ADMIN}/admins/{me['id']}").status_code == 403
    second = superadmin.post(f"{ADMIN}/admins", json={"email": "two@qpi-admin.edu", "full_name": "Second Root",
                                                       "password": ADMIN_PASSWORD, "role_id": roles["super_admin"]}).json()
    two = admin_client("two@qpi-admin.edu")
    # With two super admins, one can demote the other -- but not the last one remaining.
    assert two.patch(f"{ADMIN}/admins/{me['id']}", json={"role_id": roles["admin"]}).status_code == 200
    assert superadmin.get(f"{ADMIN}/auth/me").status_code == 401  # role change revoked the session
    assert two.patch(f"{ADMIN}/admins/{second['id']}", json={"role_id": roles["admin"]}).status_code == 403  # self
    assert two.delete(f"{ADMIN}/admins/{me['id']}").status_code == 204
    assert "ADMIN_DELETE" in _actions()


# ------------------------------------------------------------------ users
def test_user_list_search_filter_sort_paginate(superadmin):
    r = superadmin.get(f"{ADMIN}/users", params={"limit": 2, "sort": "email", "order": "asc"})
    body = r.json()
    assert r.status_code == 200 and body["total"] == 5 and body["total_pages"] == 3 and len(body["items"]) == 2
    assert body["items"][0]["email"] == "archivist@test.edu"
    assert "password_hash" not in body["items"][0]
    assert superadmin.get(f"{ADMIN}/users", params={"search": "head"}).json()["total"] == 1
    assert superadmin.get(f"{ADMIN}/users", params={"role": "FACULTY"}).json()["total"] == 3
    assert superadmin.get(f"{ADMIN}/users", params={"search": "%"}).json()["total"] == 0  # wildcards escaped
    assert superadmin.get(f"{ADMIN}/users", params={"sort": "password_hash"}).status_code == 422
    assert superadmin.get(f"{ADMIN}/users", params={"role": "GOD"}).status_code == 422
    assert superadmin.get(f"{ADMIN}/users", params={"from": "2026-02-01", "to": "2026-01-01"}).status_code == 422
    assert superadmin.get(f"{ADMIN}/users/not-a-uuid").status_code == 404


def test_user_detail_edit_and_status_changes(superadmin):
    faculty = make_client("faculty@test.edu")
    assert upload(faculty, pdf_bytes(DRAFT)).status_code == 202
    uid = _user_id("faculty@test.edu")
    detail = superadmin.get(f"{ADMIN}/users/{uid}").json()
    assert detail["stats"]["papers_total"] == 1 and detail["recent_papers"][0]["course_code"] == "PHY-201"
    assert detail["last_login_at"] is not None and detail["recent_activity"]

    r = superadmin.patch(f"{ADMIN}/users/{uid}", json={"full_name": "Dr Renamed", "email": "OTHER@test.edu"})
    assert r.status_code == 409
    r = superadmin.patch(f"{ADMIN}/users/{uid}", json={"full_name": "Dr Renamed"})
    assert r.status_code == 200 and r.json()["full_name"] == "Dr Renamed"
    assert superadmin.patch(f"{ADMIN}/users/{uid}", json={"role": "DEPT_HEAD", "clear_department": True}).status_code == 422
    assert superadmin.patch(f"{ADMIN}/users/{uid}", json={"role": "WIZARD"}).status_code == 422

    # Revoking sessions invalidates the user's existing cookies.
    assert faculty.get("/api/v1/auth/me").status_code == 200
    assert superadmin.post(f"{ADMIN}/users/{uid}/revoke-sessions").status_code == 200
    assert faculty.get("/api/v1/auth/me").status_code == 401
    assert faculty.post("/api/v1/auth/refresh").status_code == 401
    faculty = make_client("faculty@test.edu")  # a fresh login works

    assert superadmin.post(f"{ADMIN}/users/{uid}/deactivate", json={"reason": "left"}).status_code == 200
    assert faculty.get("/api/v1/auth/me").status_code == 401
    assert TestClient(app).post("/api/v1/auth/login", json={"email": "faculty@test.edu", "password": PASSWORD}).status_code == 403
    assert superadmin.post(f"{ADMIN}/users/{uid}/deactivate", json={}).status_code == 409
    assert superadmin.post(f"{ADMIN}/users/{uid}/activate", json={}).status_code == 200

    assert superadmin.post(f"{ADMIN}/users/{uid}/reset-password", json={"new_password": "weak"}).status_code == 422
    assert superadmin.post(f"{ADMIN}/users/{uid}/reset-password", json={"new_password": "NewPassword9"}).status_code == 204
    assert TestClient(app).post("/api/v1/auth/login", json={"email": "faculty@test.edu", "password": "NewPassword9"}).status_code == 200

    # Users who own papers cannot be deleted; others can.
    assert superadmin.delete(f"{ADMIN}/users/{uid}").status_code == 409
    assert superadmin.delete(f"{ADMIN}/users/{_user_id('other@test.edu')}").status_code == 204
    assert {"USER_UPDATE", "USER_REVOKE_SESSIONS", "USER_DEACTIVATE", "USER_ACTIVATE", "USER_PASSWORD_RESET",
            "USER_DELETE"} <= set(_actions())


def test_create_user_bulk_actions_and_export(superadmin):
    with SessionLocal() as db:
        dept = str(db.scalar(select(Department.id).where(Department.code == "CS")))
    r = superadmin.post(f"{ADMIN}/users", json={"email": "new@test.edu", "full_name": "New Person",
                                                  "password": "Password123", "role": "FACULTY", "department_id": dept})
    assert r.status_code == 201 and r.json()["department"]["code"] == "CS"
    assert superadmin.post(f"{ADMIN}/users", json={"email": "new@test.edu", "full_name": "Dup", "password": "Password123"}).status_code == 409
    assert superadmin.post(f"{ADMIN}/users", json={"email": "bad", "full_name": "X Y", "password": "Password123"}).status_code == 422
    ids = [_user_id("new@test.edu"), _user_id("other@test.edu")]
    r = superadmin.post(f"{ADMIN}/users/bulk", json={"ids": ids, "action": "deactivate"})
    assert r.json()["changed"] == 2
    assert superadmin.get(f"{ADMIN}/users", params={"active": "false"}).json()["total"] == 2
    r = superadmin.get(f"{ADMIN}/users/export", params={"active": "false"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert len(lines) == 3 and "password" not in lines[0]


# ------------------------------------------------------------------ papers
def test_paper_management(superadmin):
    faculty = make_client("faculty@test.edu")
    paper_id = upload(faculty, pdf_bytes(DRAFT)).json()["paper_id"]
    listing = superadmin.get(f"{ADMIN}/papers", params={"status": "COMPLETED"}).json()
    assert listing["total"] == 1 and listing["items"][0]["uploader"]["email"] == "faculty@test.edu"
    assert superadmin.get(f"{ADMIN}/papers", params={"search": "faculty@test"}).json()["total"] == 1
    assert superadmin.get(f"{ADMIN}/papers", params={"archive": "true"}).json()["total"] == 0
    assert superadmin.get(f"{ADMIN}/papers", params={"status": "NOPE"}).status_code == 422

    detail = superadmin.get(f"{ADMIN}/papers/{paper_id}").json()
    assert detail["report"]["total_questions"] == 2 and len(detail["questions"]) == 2 and "file_path" not in detail
    assert detail["can_approve"] and detail["can_reanalyze"]

    r = superadmin.get(f"{ADMIN}/papers/{paper_id}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert superadmin.post(f"{ADMIN}/papers/{paper_id}/mark-failed", json={}).status_code == 409
    assert superadmin.post(f"{ADMIN}/papers/{paper_id}/reanalyze").status_code == 202
    assert superadmin.get(f"{ADMIN}/papers/{paper_id}").json()["status"] == "COMPLETED"
    assert superadmin.post(f"{ADMIN}/papers/{paper_id}/approve").json()["status"] == "APPROVED"
    assert superadmin.post(f"{ADMIN}/papers/{paper_id}/approve").status_code == 409
    assert superadmin.post(f"{ADMIN}/papers/{paper_id}/reanalyze").status_code == 409

    files = superadmin.get(f"{ADMIN}/files").json()
    assert files["summary"]["total_files"] == 1 and "file_path" not in files["items"][0]

    csv_text = superadmin.get(f"{ADMIN}/papers/export").text
    assert "PHY-201" in csv_text

    assert superadmin.delete(f"{ADMIN}/papers/{paper_id}").status_code == 204
    assert superadmin.get(f"{ADMIN}/papers/{paper_id}").status_code == 404
    assert faculty.get(f"/api/v1/papers/{paper_id}").status_code == 404
    assert {"PAPER_DOWNLOAD", "PAPER_REANALYZE", "PAPER_APPROVE", "PAPER_DELETE", "EXPORT_PAPERS"} <= set(_actions())


def test_bulk_paper_actions_and_mark_failed(superadmin):
    faculty = make_client("faculty@test.edu")
    a = upload(faculty, pdf_bytes(DRAFT)).json()["paper_id"]
    b = upload(faculty, pdf_bytes(DRAFT + ["3. Define entropy. (5 marks)"])).json()["paper_id"]
    with SessionLocal() as db:
        db.get(QuestionPaperDraft, uuid.UUID(b)).status = PaperStatus.QUEUED
        db.commit()
    r = superadmin.post(f"{ADMIN}/papers/{b}/mark-failed", json={"reason": "Stuck in queue"})
    assert r.status_code == 200 and r.json()["status"] == "FAILED" and r.json()["error_message"] == "Stuck in queue"
    r = superadmin.post(f"{ADMIN}/papers/bulk", json={"ids": [a, b], "action": "delete"})
    assert sorted(r.json()["done"]) == sorted([a, b])
    assert superadmin.get(f"{ADMIN}/papers").json()["total"] == 0


# ------------------------------------------------------------------ catalog
def test_catalog_management(superadmin):
    r = superadmin.post(f"{ADMIN}/departments", json={"code": "bio", "name": "Biology"})
    assert r.status_code == 201 and r.json()["code"] == "BIO"
    dept = r.json()["id"]
    assert superadmin.post(f"{ADMIN}/departments", json={"code": "BIO", "name": "Dup"}).status_code == 409
    assert superadmin.post(f"{ADMIN}/departments", json={"code": "!", "name": "Bad"}).status_code == 422
    r = superadmin.post(f"{ADMIN}/courses", json={"department_id": dept, "code": "bio-101", "title": "Cells", "academic_year": "2025-2026"})
    assert r.status_code == 201 and r.json()["code"] == "BIO-101"
    course = r.json()["id"]
    assert superadmin.post(f"{ADMIN}/courses", json={"department_id": dept, "code": "BIO-101", "title": "Dup",
                                                      "academic_year": "2025-2026"}).status_code == 409
    assert superadmin.post(f"{ADMIN}/courses", json={"department_id": dept, "code": "BIO-102", "title": "Bad year",
                                                      "academic_year": "2025"}).status_code == 422
    assert superadmin.patch(f"{ADMIN}/courses/{course}", json={"title": "Cell Biology"}).json()["title"] == "Cell Biology"

    bad = {"units": [{"unit_number": 1, "title": "A", "target_weightage_percent": 50, "keywords": []}]}
    assert superadmin.put(f"{ADMIN}/courses/{course}/syllabus", json=bad).status_code == 422
    good = {"units": [{"unit_number": 1, "title": "Membranes", "target_weightage_percent": 60, "keywords": ["Lipid"]},
                      {"unit_number": 2, "title": "Organelles", "target_weightage_percent": 40, "keywords": []}]}
    units = superadmin.put(f"{ADMIN}/courses/{course}/syllabus", json=good).json()
    assert [u["keywords"] for u in units] == [["lipid"], []]
    assert superadmin.get(f"{ADMIN}/courses/{course}").json()["unit_count"] == 2

    assert superadmin.delete(f"{ADMIN}/departments/{dept}").status_code == 409  # still has a course
    with SessionLocal() as db:
        phy_course = str(db.scalar(select(Course.id).where(Course.code == "PHY-201")))
    upload(make_client("faculty@test.edu"), pdf_bytes(DRAFT))
    assert superadmin.delete(f"{ADMIN}/courses/{phy_course}").status_code == 409  # has papers
    assert superadmin.delete(f"{ADMIN}/courses/{course}").status_code == 204
    assert superadmin.delete(f"{ADMIN}/departments/{dept}").status_code == 204


# ------------------------------------------------------------------ settings
def test_runtime_settings_are_validated_and_enforced(superadmin, client):
    settings_list = superadmin.get(f"{ADMIN}/settings").json()
    assert {s["key"] for s in settings_list} >= {"registration_enabled", "uploads_enabled", "exact_match_threshold"}
    assert not any("secret" in s["key"] or "database" in s["key"] for s in settings_list)
    assert superadmin.put(f"{ADMIN}/settings", json={"values": {"jwt_secret_key": "x"}}).status_code == 422
    assert superadmin.put(f"{ADMIN}/settings", json={"values": {"max_upload_size_mb": 0}}).status_code == 422
    assert superadmin.put(f"{ADMIN}/settings", json={"values": {"conceptual_match_threshold": 0.95}}).status_code == 422
    assert superadmin.put(f"{ADMIN}/settings", json={"values": {"uploads_enabled": "no"}}).status_code == 422

    r = superadmin.put(f"{ADMIN}/settings", json={"values": {"registration_enabled": False, "uploads_enabled": False}})
    assert r.status_code == 200
    reg = client.post("/api/v1/auth/register", json={"email": "x@test.edu", "full_name": "X Person", "password": "Password123"})
    assert reg.status_code == 403
    assert upload(make_client("faculty@test.edu"), pdf_bytes(DRAFT)).status_code == 503

    superadmin.put(f"{ADMIN}/settings", json={"values": {"uploads_enabled": None, "exact_match_threshold": 0.95}})
    faculty = make_client("faculty@test.edu")
    paper_id = upload(faculty, pdf_bytes(DRAFT)).json()["paper_id"]
    report_id = faculty.get(f"/api/v1/papers/{paper_id}").json()["report_id"]
    assert faculty.get(f"/api/v1/reports/{report_id}").json()["scan"]["thresholds"]["exact"] == 0.95
    values = {s["key"]: s for s in superadmin.get(f"{ADMIN}/settings").json()}
    assert values["uploads_enabled"]["value"] is True and not values["uploads_enabled"]["is_overridden"]
    assert values["registration_enabled"]["updated_by"] == "Root"
    assert "SETTINGS_UPDATE" in _actions()


# ------------------------------------------------------------------ dashboard, reports, audit, search
def test_dashboard_and_reports_use_real_data(superadmin):
    faculty = make_client("faculty@test.edu")
    upload(faculty, pdf_bytes(DRAFT))
    s = superadmin.get(f"{ADMIN}/dashboard/summary").json()
    assert s["users"]["total"] == 5 and s["papers"]["drafts_total"] == 1 and s["content"]["questions"] == 2
    assert s["papers"]["analyzed"] == 1 and s["activity"]["user_logins_today"] >= 1
    for rng in ("today", "7d", "30d", "90d", "180d", "365d"):
        ts = superadmin.get(f"{ADMIN}/dashboard/timeseries", params={"range": rng}).json()
        assert len(ts["labels"]) == len(ts["series"]["uploads"])
    ts = superadmin.get(f"{ADMIN}/dashboard/timeseries", params={"range": "7d"}).json()
    assert sum(ts["series"]["uploads"]) == 1 and sum(ts["series"]["signups"]) == 5
    assert superadmin.get(f"{ADMIN}/dashboard/timeseries", params={"range": "custom"}).status_code == 422
    assert superadmin.get(f"{ADMIN}/dashboard/timeseries", params={"range": "forever"}).status_code == 422
    custom = superadmin.get(f"{ADMIN}/dashboard/timeseries", params={"range": "custom", "from": "2026-01-01", "to": "2026-12-31"})
    assert custom.json()["bucket"] == "month"
    dist = superadmin.get(f"{ADMIN}/dashboard/distribution").json()
    assert dist["paper_status"] == {"COMPLETED": 1} and dist["user_roles"]["FACULTY"] == 3
    assert superadmin.get(f"{ADMIN}/dashboard/activity").json()["recent_uploads"][0]["course_code"] == "PHY-201"
    assert superadmin.get(f"{ADMIN}/dashboard/alerts").status_code == 200

    rep = superadmin.get(f"{ADMIN}/reports/overview", params={"range": "30d"}).json()
    assert rep["by_course"][0]["code"] == "PHY-201" and rep["by_department"][0]["papers"] == 1
    assert sum(rep["blooms_levels"].values()) == 2
    for kind in ("departments", "courses", "uploaders"):
        r = superadmin.get(f"{ADMIN}/reports/{kind}/export", params={"range": "30d"})
        assert r.status_code == 200 and len(r.text.strip().splitlines()) == 2
    assert superadmin.get(f"{ADMIN}/reports/secrets/export").status_code == 404


def test_audit_log_is_read_only_and_filterable(superadmin):
    superadmin.post(f"{ADMIN}/departments", json={"code": "ART", "name": "Arts"})
    logs = superadmin.get(f"{ADMIN}/audit-logs", params={"actor_type": "admin"}).json()
    actions = [i["action"] for i in logs["items"]]
    assert "DEPARTMENT_CREATE" in actions and "ADMIN_LOGIN" in actions
    entry = logs["items"][0]
    assert entry["actor"]["type"] == "admin" and len(entry["ip_hash"]) == 12
    assert superadmin.get(f"{ADMIN}/audit-logs", params={"action": "DEPARTMENT_CREATE"}).json()["total"] == 1
    assert "DEPARTMENT_CREATE" in superadmin.get(f"{ADMIN}/audit-logs/facets").json()["actions"]
    assert superadmin.delete(f"{ADMIN}/audit-logs/{entry['id']}").status_code in (404, 405)
    assert superadmin.put(f"{ADMIN}/audit-logs/{entry['id']}", json={}).status_code in (404, 405)
    assert superadmin.get(f"{ADMIN}/audit-logs/export").status_code == 200


def test_global_search_and_system_health(superadmin):
    results = superadmin.get(f"{ADMIN}/search", params={"q": "phy"}).json()
    assert results["courses"][0]["title"] == "PHY-201" and results["departments"]
    assert superadmin.get(f"{ADMIN}/search", params={"q": "x"}).status_code == 422
    health = superadmin.get(f"{ADMIN}/system/health").json()
    assert health["database"]["status"] == "ok"
    flat = str(health).lower()
    assert "sqlite:///" not in flat and "secret" not in flat
