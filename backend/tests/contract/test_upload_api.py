from tests.helpers import pdf_bytes, upload

DRAFT_LINES = [
    "SECTION A",
    "1. Define Newton's law of inertia. (5 marks)",
    "2. Calculate the trajectory of a projectile launched at 45 degrees with speed 20 m/s. (10 marks)",
    "3. State the second law of thermodynamics and explain entropy. (10 marks)",
]


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert "similarity_thresholds" in data


def test_upload_requires_authentication(client):
    response = upload(client, pdf_bytes(DRAFT_LINES))
    assert response.status_code == 401


def test_paper_upload_and_status_contract(faculty_client):
    response = upload(faculty_client, pdf_bytes(DRAFT_LINES), filename="physics_draft.pdf")

    assert response.status_code == 202
    res_data = response.json()
    assert set(res_data) == {"paper_id", "status", "status_url"}
    assert res_data["status"] == "QUEUED"
    paper_id = res_data["paper_id"]
    assert res_data["status_url"] == f"/api/v1/papers/{paper_id}/status"

    # TestClient runs background tasks before returning, so processing has finished.
    status_resp = faculty_client.get(res_data["status_url"])
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["paper_id"] == paper_id
    assert status_data["status"] == "COMPLETED"
    assert status_data["progress_percent"] == 100
    assert status_data["report_id"]


def test_report_contract(faculty_client):
    paper_id = upload(faculty_client, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    report_id = faculty_client.get(f"/api/v1/papers/{paper_id}/status").json()["report_id"]

    report = faculty_client.get(f"/api/v1/reports/{report_id}").json()
    for key in ("report_id", "paper_id", "originality_score", "total_questions", "matched_questions_count", "matched_questions"):
        assert key in report
    assert report["paper_id"] == paper_id
    assert report["total_questions"] == 3
    # No archive yet: first paper for the course (spec EC-003).
    assert report["originality_score"] == 100.0
    assert report["scan"]["scope"] == "NONE"
    assert [q["question_number"] for q in report["questions"]] == ["1", "2", "3"]

    insights = faculty_client.get(f"/api/v1/reports/{report_id}/insights").json()
    for key in ("draft_freshness_score", "unit_coverage", "blooms_distribution", "overused_topics", "recommendations"):
        assert key in insights
    units = {u["title"]: u for u in insights["unit_coverage"]["units"]}
    assert units["Kinematics"]["question_count"] == 1
    assert units["Thermodynamics"]["question_count"] == 1


def test_upload_validation_errors(faculty_client):
    assert upload(faculty_client, b"plain text", filename="notes.txt").status_code == 415
    assert upload(faculty_client, b"not really a pdf", filename="fake.pdf").status_code == 400
    bad_year = upload(faculty_client, pdf_bytes(DRAFT_LINES), academic_year="2025")
    assert bad_year.status_code == 422
    assert "Academic year" in bad_year.json()["detail"]
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES), term="Winter").status_code == 422
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES), total_marks=0).status_code == 422
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES), course_code="!!").status_code == 422
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES), department_code="NOPE").status_code == 422


def test_encrypted_pdf_fails_with_clear_message(faculty_client):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), "1. Secret question (5 marks)")
    encrypted = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    paper_id = upload(faculty_client, encrypted).json()["paper_id"]
    status = faculty_client.get(f"/api/v1/papers/{paper_id}/status").json()
    assert status["status"] == "FAILED"
    assert "encrypted" in status["error_message"].lower()


def test_document_without_questions_fails(faculty_client):
    paper_id = upload(faculty_client, pdf_bytes(["Just a cover page with no numbered questions."])).json()["paper_id"]
    status = faculty_client.get(f"/api/v1/papers/{paper_id}/status").json()
    assert status["status"] == "FAILED"
    assert "No questions" in status["error_message"]


def test_duplicate_upload_conflicts(faculty_client):
    content = pdf_bytes(DRAFT_LINES)
    assert upload(faculty_client, content).status_code == 202
    assert upload(faculty_client, content).status_code == 409


def test_oversized_upload_rejected(faculty_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES)).status_code == 413
