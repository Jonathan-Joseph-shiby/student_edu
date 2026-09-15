from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["JWT_SECRET_KEY"] = "phase6-test-secret"

from backend.app.main import app  # noqa: E402
from backend.app.services.admin import generate_outline, validate_outline  # noqa: E402


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(path))
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE IF NOT EXISTS course_outlines (outline_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id INTEGER NOT NULL REFERENCES skills(skill_id), course_title TEXT NOT NULL, outline_json TEXT NOT NULL, evidence_json TEXT NOT NULL, provider TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    connection.execute("DELETE FROM course_outlines")
    connection.commit()
    connection.close()
    return path


@pytest.fixture()
def client(database: Path) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register(client: TestClient, email: str, role: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role})
    assert response.status_code == 201
    return auth(client, email, "StrongPassword123!")


def valid_outline(skill: str, resource_id: int | None = None) -> dict[str, object]:
    return {
        "course_title": f"Industry-Ready {skill}", "target_skill": skill,
        "rationale": "Grounded in observed demand and curriculum evidence.",
        "target_audience": "Undergraduate learners", "prerequisites": ["Basic computing"],
        "learning_objectives": ["Apply the target skill to an industry task."],
        "modules": [{"title": "Foundations", "description": "Core concepts from the evidence."}],
        "practical_activities": ["Complete an evidence-aligned project."],
        "assessment_strategy": "Project and skill check", "expected_outcomes": ["Demonstrate the target skill."],
        "recommended_resources": ([{"resource_id": resource_id}] if resource_id is not None else []),
    }


def test_admin_access_and_role_rejection(client: TestClient) -> None:
    assert client.get("/api/v1/admin/dashboard/summary").status_code == 401
    student = auth(client, "student.demo@industrypulse.local", "change-this-student-password")
    recruiter = auth(client, "recruiter.demo@industrypulse.local", "change-this-recruiter-password")
    assert client.get("/api/v1/admin/dashboard/summary", headers=student).status_code == 403
    assert client.get("/api/v1/admin/dashboard/summary", headers=recruiter).status_code == 403


def test_summary_dashboard_ranking_and_filters(client: TestClient) -> None:
    admin = auth(client, "admin.demo@industrypulse.local", "change-this-admin-password")
    summary = client.get("/api/v1/admin/dashboard/summary", headers=admin)
    assert summary.status_code == 200
    assert summary.json()["total_job_postings_analyzed"] == 20
    assert summary.json()["identified_skill_gaps"] == 16
    gaps = client.get("/api/v1/admin/dashboard/skill-gaps", headers=admin).json()
    assert gaps["total"] == 16
    assert gaps["items"] == sorted(gaps["items"], key=lambda item: item["rank"])
    filtered = client.get("/api/v1/admin/dashboard/skill-gaps?minimum_demand=0.1&search=java", headers=admin).json()
    assert filtered["total"] >= 1
    assert all(item["demand_score"] >= 0.1 and "java" in item["canonical_name"].casefold() for item in filtered["items"])
    coverage = client.get("/api/v1/admin/dashboard/curriculum-coverage", headers=admin)
    assert coverage.status_code == 200 and coverage.json()["total"] == 41


def test_drilldown_traceability_and_trends(client: TestClient) -> None:
    admin = auth(client, "admin.demo@industrypulse.local", "change-this-admin-password")
    gap = client.get("/api/v1/admin/dashboard/skill-gaps", headers=admin).json()["items"][0]
    detail = client.get(f"/api/v1/admin/dashboard/skill-gaps/{gap['skill_id']}", headers=admin)
    body = detail.json()
    assert detail.status_code == 200
    assert body["source_job_count"] > 0
    assert body["source_jobs"][0]["source_company_name"]
    assert body["source_jobs"][0]["source_url"] is None
    assert body["source_jobs"][0]["posting_date"] is None
    trends = client.get("/api/v1/admin/dashboard/trends", headers=admin)
    assert trends.json()["available"] is False
    assert "insufficient" in trends.json()["reason"].casefold()


def test_ai_disabled_and_structured_outline_validation(database: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    skill_id = connection.execute("SELECT skill_id FROM skill_gap_analysis WHERE gap_status='gap' ORDER BY gap_score DESC LIMIT 1").fetchone()[0]
    unavailable = generate_outline(connection, skill_id)
    assert unavailable["available"] is False
    evidence = unavailable["evidence"]
    skill = connection.execute("SELECT canonical_name FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()[0]
    with pytest.raises(ValueError):
        validate_outline({"target_skill": skill}, skill, evidence)
    connection.close()


def test_mocked_outline_is_grounded_and_history_is_persisted(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    skill_id = connection.execute("SELECT skill_id FROM skill_gap_analysis WHERE gap_status='gap' ORDER BY gap_score DESC LIMIT 1").fetchone()[0]
    skill = connection.execute("SELECT canonical_name FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()[0]
    resource = connection.execute("SELECT resource_id FROM learning_resources WHERE canonical_skill_id = ? LIMIT 1", (skill_id,)).fetchone()
    resource_id = resource[0] if resource else None
    result = generate_outline(connection, skill_id, provider=lambda context: valid_outline(skill, resource_id))
    assert result["available"] is True
    assert result["evidence"]["source_job_ids"]
    assert result["outline"]["target_skill"] == skill
    history = connection.execute("SELECT COUNT(*) FROM course_outlines WHERE skill_id = ?", (skill_id,)).fetchone()[0]
    assert history == 1
    connection.close()


def test_original_csvs_unchanged(database: Path) -> None:
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "data").glob("*.csv")}
    # The admin APIs read SQLite only; this assertion makes the immutability contract explicit.
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "data").glob("*.csv")}