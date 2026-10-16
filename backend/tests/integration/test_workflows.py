from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE
from tests.helpers import PASSWORD, make_client, pdf_bytes, upload

ARCHIVE_LINES = [
    "1. Calculate the trajectory of a projectile launched at 45 degrees with speed 20 m/s. (10 marks)",
    "2. A 5 kg block is pushed across a frictionless surface with a force of 20 N. Calculate its acceleration. (10 marks)",
    "3. State the second law of thermodynamics. (10 marks)",
]
DRAFT_LINES = [
    "1. Calculate the trajectory of a projectile launched at 45 degrees with speed 20 m/s. (10 marks)",
    "2. Explain the working of a Carnot heat engine and its efficiency. (10 marks)",
    "3. Design an experiment to measure friction between two surfaces and evaluate its errors. (10 marks)",
]


def _archive_paper(term="Fall", year="2023-2024"):
    archivist = make_client("archivist@test.edu")
    resp = upload(archivist, pdf_bytes(ARCHIVE_LINES), academic_year=year, term=term, is_historical_archive="true")
    assert resp.status_code == 202, resp.text
    return resp.json()["paper_id"]


def _report_id(client, paper_id):
    status = client.get(f"/api/v1/papers/{paper_id}/status").json()
    assert status["status"] == "COMPLETED", status
    return status["report_id"]


# ------------------------------------------------------------------ auth
def test_register_login_me_logout_flow(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "New.User@Test.edu", "full_name": "New User", "password": "Secret123", "department_code": "CS",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "new.user@test.edu"
    assert body["role"] == "FACULTY"
    assert body["department"]["code"] == "CS"
    assert ACCESS_COOKIE in client.cookies and REFRESH_COOKIE in client.cookies

    assert client.get("/api/v1/auth/me").json()["full_name"] == "New User"
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401

    assert client.post("/api/v1/auth/login", json={"email": "new.user@test.edu", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "new.user@test.edu", "password": "Secret123"}).status_code == 200


def test_register_validation_and_duplicates(client):
    dup = client.post("/api/v1/auth/register", json={"email": "faculty@test.edu", "full_name": "X Y", "password": "Secret123"})
    assert dup.status_code == 409
    weak = client.post("/api/v1/auth/register", json={"email": "a@test.edu", "full_name": "X Y", "password": "short"})
    assert weak.status_code == 422
    assert "password" in weak.json()["detail"]
    bad_email = client.post("/api/v1/auth/register", json={"email": "nope", "full_name": "X Y", "password": "Secret123"})
    assert bad_email.status_code == 422


def test_refresh_rotates_session_and_bearer_token_works(client):
    make = client.post("/api/v1/auth/login", json={"email": "faculty@test.edu", "password": PASSWORD})
    assert make.status_code == 200
    client.cookies.delete(ACCESS_COOKIE)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200

    token = client.post("/api/v1/auth/token", data={"username": "faculty@test.edu", "password": PASSWORD}).json()["access_token"]
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_protected_endpoints_require_auth(client):
    for method, path in [
        ("get", "/api/v1/papers"), ("get", "/api/v1/dashboard/stats"), ("get", "/api/v1/courses"),
        ("get", "/api/v1/reports/00000000-0000-0000-0000-000000000000"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path
    assert client.get("/api/v1/departments").status_code == 200


# ------------------------------------------------------------------ matching & reports
def test_draft_is_matched_against_historical_archive():
    _archive_paper()
    faculty = make_client("faculty@test.edu")
    paper_id = upload(faculty, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    report = faculty.get(f"/api/v1/reports/{_report_id(faculty, paper_id)}").json()

    assert report["scan"]["scope"] == "COURSE"
    assert report["scan"]["historical_papers_searched"] == 1
    assert report["scan"]["archive_year_range"] == "2023-2024"
    matched = {m["question_number"]: m for m in report["matched_questions"]}
    assert matched["1"]["match_tier"] == "EXACT"
    assert matched["1"]["source"]["question_number"] == "1"
    assert matched["1"]["source_paper"] == "Fall 2023 Final Examination"
    assert report["matched_questions_count"] == len(report["matched_questions"])
    # Q1 carries a third of the marks and is an exact repeat.
    assert report["originality_score"] < 70

    insights = faculty.get(f"/api/v1/reports/{report['report_id']}/insights").json()
    assert insights["recommendations"][0]["category"] == "REPETITION_SWAP"
    assert insights["recommendations"][0]["target_question_number"] == "1"


def test_approved_papers_join_the_archive():
    faculty = make_client("faculty@test.edu")
    first = upload(faculty, pdf_bytes(ARCHIVE_LINES), academic_year="2024-2025").json()["paper_id"]
    assert faculty.post(f"/api/v1/papers/{first}/approve").json()["status"] == "APPROVED"
    assert faculty.post(f"/api/v1/papers/{first}/approve").status_code == 409

    other = make_client("other@test.edu")
    second = upload(other, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    report = other.get(f"/api/v1/reports/{_report_id(other, second)}").json()
    assert report["scan"]["historical_papers_searched"] == 1
    assert report["matched_questions"]


def test_revision_links_to_previous_report():
    _archive_paper()
    faculty = make_client("faculty@test.edu")
    first = upload(faculty, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    first_report = faculty.get(f"/api/v1/reports/{_report_id(faculty, first)}").json()

    revised_lines = [
        "1. A flywheel slows from 30 rad/s to rest in 10 s. Determine the angular deceleration. (10 marks)",
        *DRAFT_LINES[1:],
    ]
    second = upload(faculty, pdf_bytes(revised_lines), previous_paper_id=first).json()["paper_id"]
    report = faculty.get(f"/api/v1/reports/{_report_id(faculty, second)}").json()
    assert report["paper"]["previous_paper_id"] == first
    assert report["previous_report"]["originality_score"] == first_report["originality_score"]
    assert report["originality_score"] > first_report["originality_score"]


def test_revision_of_someone_elses_paper_is_rejected():
    faculty = make_client("faculty@test.edu")
    first = upload(faculty, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    other = make_client("other@test.edu")
    assert upload(other, pdf_bytes(ARCHIVE_LINES), previous_paper_id=first).status_code == 404


# ------------------------------------------------------------------ RBAC
def test_faculty_cannot_see_other_faculty_papers_but_dept_head_can():
    faculty = make_client("faculty@test.edu")
    paper_id = upload(faculty, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    report_id = _report_id(faculty, paper_id)

    other = make_client("other@test.edu")
    assert other.get(f"/api/v1/papers/{paper_id}").status_code == 404
    assert other.get(f"/api/v1/reports/{report_id}").status_code == 404
    assert other.delete(f"/api/v1/papers/{paper_id}").status_code == 404
    assert other.get("/api/v1/papers").json()["total"] == 0

    head = make_client("head@test.edu")
    assert head.get(f"/api/v1/reports/{report_id}").status_code == 200
    assert head.get("/api/v1/papers").json()["total"] == 1
    assert head.delete(f"/api/v1/papers/{paper_id}").status_code == 403

    cs_faculty = make_client("csfaculty@test.edu")
    assert cs_faculty.get(f"/api/v1/reports/{report_id}").status_code == 404


def test_only_archive_roles_can_ingest_historical_papers(faculty_client):
    resp = upload(faculty_client, pdf_bytes(ARCHIVE_LINES), is_historical_archive="true")
    assert resp.status_code == 403


def test_malformed_ids_return_404(faculty_client):
    assert faculty_client.get("/api/v1/papers/not-a-uuid").status_code == 404
    assert faculty_client.get("/api/v1/reports/not-a-uuid/insights").status_code == 404


# ------------------------------------------------------------------ list / delete / reanalyze / download
def test_list_search_filter_sort_and_paginate(faculty_client):
    for i, year in enumerate(["2023-2024", "2024-2025", "2025-2026"]):
        lines = [f"{n}. Question {n} about projectile velocity number {i}. (10 marks)" for n in range(1, 3)]
        assert upload(faculty_client, pdf_bytes(lines), academic_year=year, filename=f"draft{i}.pdf").status_code == 202

    page1 = faculty_client.get("/api/v1/papers", params={"limit": 2, "page": 1}).json()
    assert page1["total"] == 3 and page1["pages"] == 2 and len(page1["items"]) == 2
    page2 = faculty_client.get("/api/v1/papers", params={"limit": 2, "page": 2}).json()
    assert len(page2["items"]) == 1

    search = faculty_client.get("/api/v1/papers", params={"search": "draft1"}).json()
    assert [p["original_filename"] for p in search["items"]] == ["draft1.pdf"]
    by_year = faculty_client.get("/api/v1/papers", params={"sort": "academic_year", "order": "asc"}).json()
    assert [p["academic_year"] for p in by_year["items"]] == ["2023-2024", "2024-2025", "2025-2026"]
    completed = faculty_client.get("/api/v1/papers", params={"status": "COMPLETED,APPROVED"}).json()
    assert completed["total"] == 3
    assert faculty_client.get("/api/v1/papers", params={"status": "BOGUS"}).status_code == 422
    assert faculty_client.get("/api/v1/papers", params={"sort": "evil"}).status_code == 422


def test_delete_reanalyze_and_download(faculty_client):
    content = pdf_bytes(DRAFT_LINES)
    paper_id = upload(faculty_client, content).json()["paper_id"]

    download = faculty_client.get(f"/api/v1/papers/{paper_id}/file")
    assert download.status_code == 200
    assert download.content == content
    assert "attachment" in download.headers["content-disposition"]

    re = faculty_client.post(f"/api/v1/papers/{paper_id}/reanalyze")
    assert re.status_code == 202
    assert faculty_client.get(f"/api/v1/papers/{paper_id}/status").json()["status"] == "COMPLETED"

    assert faculty_client.delete(f"/api/v1/papers/{paper_id}").status_code == 204
    assert faculty_client.get(f"/api/v1/papers/{paper_id}").status_code == 404
    # The same file can be uploaded again once the original is gone.
    assert upload(faculty_client, content).status_code == 202


def test_approved_paper_cannot_be_deleted_by_faculty(faculty_client):
    paper_id = upload(faculty_client, pdf_bytes(DRAFT_LINES)).json()["paper_id"]
    faculty_client.post(f"/api/v1/papers/{paper_id}/approve")
    assert faculty_client.delete(f"/api/v1/papers/{paper_id}").status_code == 409
    assert faculty_client.post(f"/api/v1/papers/{paper_id}/reanalyze").status_code == 409


# ------------------------------------------------------------------ dashboard / catalog
def test_dashboard_stats_reflect_real_data(faculty_client):
    empty = faculty_client.get("/api/v1/dashboard/stats").json()
    assert empty["total_analyzed"] == 0 and empty["avg_originality"] is None

    _archive_paper()
    upload(faculty_client, pdf_bytes(DRAFT_LINES))
    upload(faculty_client, pdf_bytes(["1. A totally unrelated question about optics and lenses. (10 marks)"]))
    stats = faculty_client.get("/api/v1/dashboard/stats").json()
    assert stats["total_analyzed"] == 2  # archive ingests are excluded
    assert stats["analyzed_last_30_days"] == 2
    assert 0 < stats["avg_originality"] < 100
    assert stats["total_matches"] >= 1


def test_courses_and_syllabus_management(faculty_client):
    courses = faculty_client.get("/api/v1/courses", params={"department_code": "PHY"}).json()
    assert [c["code"] for c in courses] == ["PHY-201"]
    course_id = courses[0]["id"]
    assert len(faculty_client.get(f"/api/v1/courses/{course_id}/syllabus").json()) == 3

    payload = {"units": [{"unit_number": 1, "title": "Optics", "target_weightage_percent": 100, "keywords": ["Lens"]}]}
    assert faculty_client.put(f"/api/v1/courses/{course_id}/syllabus", json=payload).status_code == 403

    head = make_client("head@test.edu")
    bad = {"units": [{"unit_number": 1, "title": "Optics", "target_weightage_percent": 50}]}
    assert head.put(f"/api/v1/courses/{course_id}/syllabus", json=bad).status_code == 422
    updated = head.put(f"/api/v1/courses/{course_id}/syllabus", json=payload).json()
    assert updated[0]["keywords"] == ["lens"]


def test_new_course_is_created_on_upload(faculty_client):
    assert upload(faculty_client, pdf_bytes(DRAFT_LINES), course_code="phy-305").status_code == 202
    codes = [c["code"] for c in faculty_client.get("/api/v1/courses").json()]
    assert "PHY-305" in codes


def test_full_flow_with_database_storage(faculty_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_TYPE", "database")
    content = pdf_bytes(DRAFT_LINES)
    paper_id = upload(faculty_client, content).json()["paper_id"]
    assert faculty_client.get(f"/api/v1/papers/{paper_id}/status").json()["status"] == "COMPLETED"
    assert faculty_client.get(f"/api/v1/papers/{paper_id}/file").content == content
    assert faculty_client.delete(f"/api/v1/papers/{paper_id}").status_code == 204
