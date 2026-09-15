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
os.environ["JWT_SECRET_KEY"] = "phase4-test-secret"

from backend.app.main import app  # noqa: E402
from backend.app.services.student import level_for_score  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(path))
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM assessment_answers")
    connection.execute("DELETE FROM student_skill_scores")
    connection.execute("DELETE FROM assessment_attempts")
    connection.execute("DELETE FROM student_target_roles")
    connection.execute("DELETE FROM student_progress")
    connection.commit()
    connection.close()
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str, role: str = "student", student_id: str | None = "S001") -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role, "student_id": student_id})
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert login.status_code == 200
    return login.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_profile_isolation_and_role_protection(client: TestClient) -> None:
    student = register_and_login(client, "s001.phase4@example.com", student_id="S001")
    other = register_and_login(client, "s002.phase4@example.com", student_id="S002")
    recruiter = register_and_login(client, "r.phase4@example.com", role="recruiter", student_id=None)
    assert client.get("/api/v1/student/profile", headers=headers(student)).json()["student_id"] == "S001"
    assert client.get("/api/v1/student/profile", headers=headers(other)).json()["student_id"] == "S002"
    assert client.get("/api/v1/student/profile", headers=headers(recruiter)).status_code == 403
    assert client.get("/api/v1/student/profile").status_code == 401


def test_target_role_and_question_answers_are_private(client: TestClient) -> None:
    token = register_and_login(client, "role.phase4@example.com")
    response = client.put("/api/v1/student/target-role", headers=headers(token), json={"target_role": "Junior Data Analyst"})
    assert response.status_code == 200
    assert response.json()["required_skills"]
    questions = client.get("/api/v1/student/assessment", headers=headers(token)).json()["items"]
    assert questions
    assert all("answer" not in question for question in questions)
    assert client.put("/api/v1/student/target-role", headers=headers(token), json={"target_role": "Invented Role"}).status_code == 400


def test_score_thresholds() -> None:
    assert level_for_score(0) == "Beginner"
    assert level_for_score(39.99) == "Beginner"
    assert level_for_score(40) == "Intermediate"
    assert level_for_score(70) == "Good"
    assert level_for_score(85) == "Strong"


def test_assessment_history_and_reassessment_update_state(client: TestClient) -> None:
    token = register_and_login(client, "assessment.phase4@example.com")
    client.put("/api/v1/student/target-role", headers=headers(token), json={"target_role": "Junior Data Analyst"})
    questions = client.get("/api/v1/student/assessment", headers=headers(token)).json()["items"][:3]
    # Answers are intentionally obtained from the source database only in the test,
    # never exposed by the student question endpoint.
    source = sqlite3.connect(ROOT / "db" / "industrypulse.sqlite3")
    answer_map = {row[0]: row[1] for row in source.execute("SELECT question_id, answer FROM assessment_questions WHERE question_id IN (?, ?, ?)", tuple(q["question_id"] for q in questions))}
    source.close()
    first = client.post("/api/v1/student/assessment/submit", headers=headers(token), json={"answers": [{"question_id": q["question_id"], "answer": answer_map[q["question_id"]]} for q in questions]})
    assert first.status_code == 200
    second = client.post("/api/v1/student/assessment/submit", headers=headers(token), json={"answers": [{"question_id": q["question_id"], "answer": "incorrect"} for q in questions]})
    assert second.status_code == 200
    assert second.json()["version"] == 2
    history = client.get("/api/v1/student/assessment/history", headers=headers(token)).json()
    assert history["total"] == 2
    latest = client.get("/api/v1/student/assessment/latest", headers=headers(token)).json()
    assert latest["version"] == 2


def test_gap_recommendations_roadmap_readiness_and_progress(client: TestClient) -> None:
    token = register_and_login(client, "journey.phase4@example.com")
    h = headers(token)
    client.put("/api/v1/student/target-role", headers=h, json={"target_role": "Junior Data Analyst"})
    gap = client.get("/api/v1/student/skill-gap", headers=h).json()
    recommendations = client.get("/api/v1/student/recommendations", headers=h).json()["items"]
    roadmap = client.get("/api/v1/student/roadmap", headers=h).json()["items"]
    readiness = client.get("/api/v1/student/readiness", headers=h).json()
    assert gap["items"]
    assert all(item["priority_score"] >= 0 for item in gap["items"])
    assert roadmap
    assert readiness["label"] == "SkillBridge Readiness Score"
    item = next(item for item in recommendations if item["resource_id"] is not None)
    progress = client.post("/api/v1/student/progress", headers=h, json={"skill_id": item["skill_id"], "resource_id": item["resource_id"], "status": "in_progress", "week_number": 1})
    assert progress.status_code == 200