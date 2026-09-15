from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
os.environ["JWT_SECRET_KEY"] = "phase10-test-secret"

from backend.app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    database_path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", database_path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(database_path))
    with TestClient(app) as test_client:
        yield test_client, database_path


def register(client: TestClient, email: str, role: str) -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role, "student_id": "S001" if role == "student" else None})
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert login.status_code == 200
    return login.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_student_list_detail_pagination_and_role_privacy(client: tuple[TestClient, Path]) -> None:
    test_client, database_path = client
    admin = register(test_client, "phase10.admin@example.test", "admin")
    student = register(test_client, "phase10.student@example.test", "student")
    recruiter = register(test_client, "phase10.recruiter@example.test", "recruiter")

    listing = test_client.get("/api/v1/admin/students?page=1&page_size=2", headers=headers(admin))
    assert listing.status_code == 200
    assert listing.json()["page_size"] == 2
    assert listing.json()["total"] == 20
    assert len(listing.json()["items"]) == 2
    assert "password_hash" not in listing.text

    detail = test_client.get("/api/v1/admin/students/S001", headers=headers(admin))
    assert detail.status_code == 200
    body = detail.json()
    assert body["profile"]["student_id"] == "S001"
    assert "password_hash" not in detail.text
    assert "latest_scores" in body and "skill_gaps" in body and "readiness" in body
    assert test_client.get("/api/v1/admin/students/does-not-exist", headers=headers(admin)).status_code == 404
    assert test_client.get("/api/v1/admin/students", headers=headers(student)).status_code == 403
    assert test_client.get("/api/v1/admin/students", headers=headers(recruiter)).status_code == 403

    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 20
    connection.close()


def test_try_it_live_modes_reuse_normalization_and_do_not_store_document_text(client: tuple[TestClient, Path]) -> None:
    test_client, database_path = client
    token = register(test_client, "phase10.tryit@example.test", "admin")
    h = headers(token)
    job_text = "Skills: Python, ReactJS, UnknownFramework. Build dashboards for real teams."
    job = test_client.post("/api/v1/try-it/job", headers=h, json={"text": job_text})
    assert job.status_code == 200
    job_body = job.json()
    canonical_names = {item["canonical_skill"] for item in job_body["skills"]}
    assert "Python" in canonical_names
    assert any(item["raw_skill"] == "UnknownFramework" for item in job_body["unresolved_skills"])
    assert job_body["stored_text"] is False

    resume = test_client.post("/api/v1/try-it/resume", headers=h, json={"text": "Skills: Python, SQL", "target_role": "Junior Data Analyst"})
    assert resume.status_code == 200
    assert resume.json()["target_role_comparison"]["target_role"] == "Junior Data Analyst"

    syllabus = test_client.post("/api/v1/try-it/syllabus", headers=h, json={"text": "Subjects: Python, Excel, Tableau"})
    assert syllabus.status_code == 200
    assert syllabus.json()["skills"]

    oversized = test_client.post("/api/v1/try-it/job", headers=h, json={"text": "x" * 12001})
    assert oversized.status_code == 422
    assert test_client.post("/api/v1/try-it/nope", headers=h, json={"text": "Python"}).status_code == 404
    assert test_client.post("/api/v1/try-it/job", json={"text": "Python"}).status_code == 401

    connection = sqlite3.connect(database_path)
    cached_text = {row[0] for row in connection.execute("SELECT raw_skill FROM skill_normalization_cache")}
    assert job_text not in cached_text
    connection.close()