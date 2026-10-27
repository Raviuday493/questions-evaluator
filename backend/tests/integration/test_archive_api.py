"""Structured archive imports and retrieval."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.admin_security import sync_system_roles
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AdminRole, AdminUser, ArchiveQuestion, ArchiveSolution
from tests.integration.test_admin_api import ADMIN_PASSWORD, admin_client

ARCHIVE = "/api/v1/admin/archive"


def create_archive_admin(email="archive-admin@test.edu", role_key="super_admin"):
    with SessionLocal() as db:
        sync_system_roles(db)
        role = db.scalar(select(AdminRole).where(AdminRole.key == role_key))
        db.add(
            AdminUser(
                email=email,
                full_name="Archive Admin",
                password_hash=hash_password(ADMIN_PASSWORD),
                role_id=role.id,
            )
        )
        db.commit()
    return admin_client(email)


def record(**changes):
    item = {
        "question": "  Compute   x² + 1.\r\nShow work. ",
        "solutions": ["x² + 1 = 5; x = ±2"],
        "subject": "Mathematics",
        "topic": "Algebra",
        "source": "Authorized sample",
        "source_reference": "set-1",
        "metadata": {"year": 2020},
    }
    item.update(changes)
    return item


def test_import_retrieval_filter_pagination_and_idempotency(client):
    admin = create_archive_admin()
    first = admin.post(f"{ARCHIVE}/imports", json=[record()])
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "created"
    second = admin.post(
        f"{ARCHIVE}/imports", json=[record(), record(solutions=["Alternative: ±2"])]
    )
    assert second.status_code == 200
    assert [item["status"] for item in second.json()["results"]] == [
        "skipped",
        "updated",
    ]
    page = admin.get(ARCHIVE, params={"topic": "Algebra", "limit": 1}).json()
    assert page["total"] == 1 and len(page["items"]) == 1
    detail = admin.get(f"{ARCHIVE}/{page['items'][0]['id']}").json()
    assert len(detail["solutions"]) == 2
    assert "x² + 1" in detail["question"]


def test_search_filter_and_page_boundaries(client):
    admin = create_archive_admin()
    entries = [
        record(
            question=f"Question number {i}",
            source_reference=f"set-{i}",
            topic="Algebra" if i < 2 else "Geometry",
        )
        for i in range(3)
    ]
    assert admin.post(f"{ARCHIVE}/imports", json=entries).status_code == 200
    first = admin.get(
        ARCHIVE, params={"limit": 1, "page": 1, "topic": "Algebra"}
    ).json()
    second = admin.get(
        ARCHIVE, params={"limit": 1, "page": 2, "topic": "Algebra"}
    ).json()
    assert first["total"] == 2 and second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert (
        admin.get(ARCHIVE, params={"search": "Question number 2"}).json()["total"] == 1
    )


def test_invalid_rows_and_size_or_shape_errors_are_reported(client):
    admin = create_archive_admin()
    result = admin.post(
        f"{ARCHIVE}/imports",
        json=[
            record(),
            {"question": "  ", "solutions": [], "source": ""},
            {"question": "missing fields"},
        ],
    )
    assert result.status_code == 200
    assert [r["status"] for r in result.json()["results"]] == [
        "created",
        "failed",
        "failed",
    ]
    assert (
        admin.post(
            f"{ARCHIVE}/imports",
            content="{bad",
            headers={"Content-Type": "application/json"},
        ).status_code
        == 400
    )
    assert (
        admin.post(
            f"{ARCHIVE}/imports",
            content='[{"question":NaN}]',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 400
    )
    assert admin.post(f"{ARCHIVE}/imports", json={"records": []}).status_code == 422
    assert admin.post(f"{ARCHIVE}/imports", json=[record()] * 501).status_code == 422
    oversized = admin.post(
        f"{ARCHIVE}/imports",
        content=b" " * (5 * 1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413


def test_import_requires_admin_auth_and_permission(client):
    assert client.post(f"{ARCHIVE}/imports", json=[record()]).status_code == 401
    assert client.get(ARCHIVE).status_code == 401
    no_import = create_archive_admin("support-archive@test.edu", "support")
    assert no_import.post(f"{ARCHIVE}/imports", json=[record()]).status_code == 403

    with SessionLocal() as db:
        role = AdminRole(
            key="archive_no_read",
            name="No archive read",
            description="",
            permissions=[],
            is_system=False,
        )
        db.add(role)
        db.flush()
        db.add(
            AdminUser(
                email="no-read@test.edu",
                full_name="No Read",
                password_hash=hash_password(ADMIN_PASSWORD),
                role_id=role.id,
            )
        )
        db.commit()
    no_read = admin_client("no-read@test.edu")
    assert no_read.get(ARCHIVE).status_code == 403


def test_failed_database_write_rolls_back_all_valid_rows(client, monkeypatch):
    admin = create_archive_admin()
    from app.api.admin import archive as archive_api

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit write failure")

    monkeypatch.setattr(archive_api.AuditService, "record_admin", fail_audit)
    with pytest.raises(RuntimeError, match="audit write failure"):
        admin.post(f"{ARCHIVE}/imports", json=[record()])
    with SessionLocal() as db:
        assert db.scalar(select(ArchiveQuestion)) is None


def test_database_constraint_prevents_duplicate_solution(client):
    admin = create_archive_admin()
    imported = admin.post(f"{ARCHIVE}/imports", json=[record()]).json()
    question_id = imported["results"][0]["question_id"]
    solution = admin.get(f"{ARCHIVE}/{question_id}").json()["solutions"][0]
    with SessionLocal() as db:
        db.add(
            ArchiveSolution(
                question_id=uuid.UUID(question_id),
                solution_text="duplicate",
                content_hash=solution["content_hash"],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
