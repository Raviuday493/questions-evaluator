"""Test configuration: an isolated SQLite database and upload directory, hashing embeddings,
and in-process background processing (TestClient runs BackgroundTasks before returning)."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="qpi-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{os.path.join(_TMP, 'test.db')}",
    "LOCAL_STORAGE_DIR": os.path.join(_TMP, "uploads"),
    "EMBEDDING_PROVIDER": "hashing",
    "TASK_QUEUE": "background",
    "JWT_SECRET_KEY": "test-secret-key-for-pytest-only-0123456789",
    "ENVIRONMENT": "development",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Course, Department, SyllabusUnit, User, UserRole  # noqa: E402
from tests.helpers import PASSWORD, login  # noqa: E402

_PASSWORD_HASH = hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def _fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        phy = Department(code="PHY", name="Department of Physics")
        cs = Department(code="CS", name="Computer Science")
        db.add_all([phy, cs])
        db.flush()
        course = Course(department_id=phy.id, code="PHY-201", title="Mechanics", academic_year="2025-2026")
        db.add(course)
        db.flush()
        db.add_all([
            SyllabusUnit(course_id=course.id, unit_number=1, title="Kinematics", target_weightage_percent=40,
                         keywords=["projectile", "velocity", "acceleration", "trajectory"]),
            SyllabusUnit(course_id=course.id, unit_number=2, title="Dynamics", target_weightage_percent=30,
                         keywords=["force", "newton", "friction"]),
            SyllabusUnit(course_id=course.id, unit_number=3, title="Thermodynamics", target_weightage_percent=30,
                         keywords=["entropy", "heat", "thermodynamics", "carnot"]),
        ])
        for email, role, dept in [
            ("faculty@test.edu", UserRole.FACULTY, phy),
            ("other@test.edu", UserRole.FACULTY, phy),
            ("csfaculty@test.edu", UserRole.FACULTY, cs),
            ("head@test.edu", UserRole.DEPT_HEAD, phy),
            ("archivist@test.edu", UserRole.ARCHIVAL_ADMIN, None),
        ]:
            db.add(User(email=email, full_name=email.split("@")[0].title(), password_hash=_PASSWORD_HASH,
                        role=role, department_id=dept.id if dept else None))
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def faculty_client(client):
    return login(client, "faculty@test.edu")

