from fastapi.testclient import TestClient

from app.main import app
from scripts.pdf_utils import build_pdf

PASSWORD = "Password123"


def login(client: TestClient, email: str) -> TestClient:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return client


def make_client(email: str) -> TestClient:
    return login(TestClient(app), email)


def pdf_bytes(lines, title="Exam") -> bytes:
    return build_pdf(lines, title=title)


def upload(client: TestClient, content: bytes, filename="draft.pdf", **fields):
    data = {
        "course_code": "PHY-201",
        "department_code": "PHY",
        "academic_year": "2025-2026",
        "term": "Fall",
        "exam_type": "Final Examination",
        "total_marks": "100",
    }
    data.update({k: str(v) for k, v in fields.items()})
    return client.post("/api/v1/papers/upload", data=data, files={"file": (filename, content, "application/pdf")})
