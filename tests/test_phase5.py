from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["JWT_SECRET_KEY"] = "phase5-test-secret"

from backend.app.main import app  # noqa: E402
from backend.app.services.recruiter import ensure_recruiter_tables  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(path))
    connection = sqlite3.connect(path)
    ensure_recruiter_tables(connection)
    connection.execute("DELETE FROM recruiter_shortlists")
    connection.execute("DELETE FROM recruiter_job_skills")
    connection.execute("DELETE FROM recruiter_jobs")
    connection.commit()
    connection.close()
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str = "change-this-recruiter-password") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def register(client: TestClient, email: str, role: str, student_id: str | None = None) -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role, "student_id": student_id})
    assert response.status_code == 201
    return client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123!"}).json()["access_token"]


def h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_job(client: TestClient, token: str, preferred: list[str] | None = None) -> dict:
    response = client.post("/api/v1/recruiter/jobs", headers=h(token), json={"title": "Phase Five Analyst", "description": "Analyze business data.", "location": "Mumbai", "company_display_name": "Independent Demo Employer", "required_skills": ["Python", "Excel"], "preferred_skills": preferred or [], "status": "open"})
    assert response.status_code == 201
    return response.json()


def test_recruiter_auth_and_student_rejection(client: TestClient) -> None:
    assert client.get("/api/v1/recruiter/jobs").status_code == 401
    student = login(client, "student.demo@industrypulse.local", "change-this-student-password")
    assert client.get("/api/v1/recruiter/jobs", headers=h(student)).status_code == 403


def test_job_creation_normalizes_alias_and_rejects_unresolved(client: TestClient) -> None:
    recruiter = login(client, "recruiter.demo@industrypulse.local")
    job = create_job(client, recruiter, ["ReactJS"])
    assert {item["skill_id"] for item in job["required_skills"]}
    assert client.post("/api/v1/recruiter/jobs", headers=h(recruiter), json={"title": "Invalid", "description": "x", "location": "Delhi", "company_display_name": "Demo", "required_skills": ["Unrecognized Quantum Tool"], "preferred_skills": [], "status": "draft"}).status_code == 400


def test_job_ownership_and_management(client: TestClient) -> None:
    first = login(client, "recruiter.demo@industrypulse.local")
    second = register(client, "other.recruiter.phase5@example.com", "recruiter")
    job = create_job(client, first)
    assert client.get("/api/v1/recruiter/jobs", headers=h(first)).json()["total"] == 1
    assert client.get(f"/api/v1/recruiter/jobs/{job['job_id']}", headers=h(second)).status_code == 404
    assert client.put(f"/api/v1/recruiter/jobs/{job['job_id']}", headers=h(second), json={"title": "Hijacked"}).status_code == 404
    assert client.delete(f"/api/v1/recruiter/jobs/{job['job_id']}", headers=h(second)).status_code == 404


def test_matching_formula_explanation_ranking_and_filters(client: TestClient) -> None:
    recruiter = login(client, "recruiter.demo@industrypulse.local")
    job = create_job(client, recruiter, ["ReactJS"])
    result = client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/matches", headers=h(recruiter)).json()
    assert result["total"] == 20
    assert result["items"] == sorted(result["items"], key=lambda item: (-item["match_score"], -item["required_skill_coverage"], -(item["readiness_score"] or 0), item["student_id"]))
    candidate = result["items"][0]
    expected = 0.8 * candidate["required_match"] + 0.2 * candidate["preferred_match"]
    assert candidate["match_score"] == round(expected, 2)
    assert "strong_matches" in candidate and "skill_gaps" in candidate
    filtered = client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/matches?min_match_score=100", headers=h(recruiter))
    assert all(item["match_score"] >= 100 for item in filtered.json()["items"])


def test_match_detail_privacy_and_admin_behavior(client: TestClient) -> None:
    recruiter = login(client, "recruiter.demo@industrypulse.local")
    job = create_job(client, recruiter)
    match = client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/matches", headers=h(recruiter)).json()["items"][0]
    detail = client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/matches/{match['student_id']}", headers=h(recruiter))
    assert detail.status_code == 200
    assert "password_hash" not in detail.json()
    assert "assessment_answers" not in detail.json()
    admin = register(client, "admin.phase5@example.com", "admin")
    assert client.get("/api/v1/recruiter/jobs", headers=h(admin)).status_code == 403


def test_shortlist_create_remove_and_retrieve(client: TestClient) -> None:
    recruiter = login(client, "recruiter.demo@industrypulse.local")
    job = create_job(client, recruiter)
    student_id = "S001"
    add = client.post(f"/api/v1/recruiter/jobs/{job['job_id']}/shortlist/{student_id}", headers=h(recruiter))
    assert add.status_code == 200
    shortlist = client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/shortlist", headers=h(recruiter))
    assert shortlist.json()["total"] == 1
    assert client.delete(f"/api/v1/recruiter/jobs/{job['job_id']}/shortlist/{student_id}", headers=h(recruiter)).status_code == 200
    assert client.get(f"/api/v1/recruiter/jobs/{job['job_id']}/shortlist", headers=h(recruiter)).json()["total"] == 0