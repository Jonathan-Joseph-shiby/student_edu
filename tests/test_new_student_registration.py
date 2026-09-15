from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
os.environ["JWT_SECRET_KEY"] = "new-student-test-secret"

from backend.app.main import app  # noqa: E402


EMAIL = "new.student.registration.2026@example.test"
PASSWORD = "NewStudentPassword123!"


@pytest.fixture()
def isolated_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    database_path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", database_path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(database_path))
    with TestClient(app) as client:
        yield client, database_path


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_new_student_registration_and_complete_workflow(isolated_client: tuple[TestClient, Path]) -> None:
    client, database_path = isolated_client
    connection = sqlite3.connect(database_path)
    before_counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ["students", "job_postings", "companies", "assessment_questions", "learning_resources", "skills", "skill_aliases", "curriculum_skill_observations"]
    }
    connection.close()

    registration = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "role": "student"})
    assert registration.status_code == 201
    user = registration.json()
    assert user["role"] == "student"
    assert user["student_id"]
    assert user["student_id"] not in {f"S{number:03d}" for number in range(1, 21)}

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    user_row = connection.execute("SELECT * FROM users WHERE email = ?", (EMAIL,)).fetchone()
    student_row = connection.execute("SELECT * FROM students WHERE student_id = ?", (user["student_id"],)).fetchone()
    assert user_row is not None
    assert user_row["role"] == "student"
    assert user_row["student_id"] == user["student_id"]
    assert user_row["password_hash"] != PASSWORD
    assert user_row["password_hash"].startswith("$argon2")
    assert student_row is not None
    assert connection.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (user["student_id"],)).fetchone()[0] == 1
    assert {row[0] for row in connection.execute("SELECT student_id FROM students WHERE student_id LIKE 'S0%'")} >= {f"S{number:03d}" for number in range(1, 21)}
    connection.close()

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["student_id"] == user["student_id"]

    profile = client.get("/api/v1/student/profile", headers=auth(token))
    assert profile.status_code == 200
    assert profile.json()["student_id"] == user["student_id"]
    updated = client.put(
        "/api/v1/student/profile",
        headers=auth(token),
        json={"name": "New Registration Student", "experience": "Development project", "certifications": "SQLite Fundamentals"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "New Registration Student"

    connection = sqlite3.connect(database_path)
    persisted = connection.execute("SELECT name, experience, certifications FROM students WHERE student_id = ?", (user["student_id"],)).fetchone()
    assert persisted == ("New Registration Student", "Development project", "SQLite Fundamentals")
    role = connection.execute("SELECT job_title FROM job_postings ORDER BY job_title LIMIT 1").fetchone()[0]
    connection.close()

    selected_role = client.put("/api/v1/student/target-role", headers=auth(token), json={"target_role": role})
    assert selected_role.status_code == 200
    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (user["student_id"],)).fetchone()[0] == role
    connection.close()

    questions = client.get("/api/v1/student/assessment", headers=auth(token))
    assert questions.status_code == 200
    first_question = questions.json()["items"][0]
    connection = sqlite3.connect(database_path)
    answer = connection.execute("SELECT answer FROM assessment_questions WHERE question_id = ?", (first_question["question_id"],)).fetchone()[0]
    connection.close()
    submission = client.post("/api/v1/student/assessment/submit", headers=auth(token), json={"answers": [{"question_id": first_question["question_id"], "answer": answer}]})
    assert submission.status_code == 200
    assert client.get("/api/v1/student/assessment/latest", headers=auth(token)).status_code == 200
    assert client.get("/api/v1/student/assessment/history", headers=auth(token)).json()["total"] == 1

    gap = client.get("/api/v1/student/skill-gap", headers=auth(token))
    recommendations = client.get("/api/v1/student/recommendations", headers=auth(token))
    roadmap = client.get("/api/v1/student/roadmap", headers=auth(token))
    readiness = client.get("/api/v1/student/readiness", headers=auth(token))
    assert gap.status_code == recommendations.status_code == roadmap.status_code == readiness.status_code == 200
    assert gap.json()["target_role"] == role
    assert isinstance(recommendations.json()["items"], list)
    assert isinstance(roadmap.json()["items"], list)
    assert readiness.json()["target_role"] == role

    connection = sqlite3.connect(database_path)
    after_counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before_counts
    }
    assert after_counts["students"] == before_counts["students"] + 1
    for table in before_counts:
        if table != "students":
            assert after_counts[table] == before_counts[table]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_duplicate_email_does_not_leave_orphan_student_profile(isolated_client: tuple[TestClient, Path]) -> None:
    client, database_path = isolated_client
    first = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "role": "student"})
    assert first.status_code == 201
    connection = sqlite3.connect(database_path)
    before = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    connection.close()

    duplicate = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "role": "student"})
    assert duplicate.status_code == 409
    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == before
    connection.close()


def test_multiple_new_students_receive_unique_ids(isolated_client: tuple[TestClient, Path]) -> None:
    client, database_path = isolated_client
    first = client.post("/api/v1/auth/register", json={"email": "new.student.one.2026@example.test", "password": PASSWORD, "role": "student"})
    second = client.post("/api/v1/auth/register", json={"email": "new.student.two.2026@example.test", "password": PASSWORD, "role": "student"})
    assert first.status_code == second.status_code == 201
    first_id = first.json()["student_id"]
    second_id = second.json()["student_id"]
    assert first_id != second_id
    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT COUNT(*) FROM students WHERE student_id IN (?, ?)", (first_id, second_id)).fetchone()[0] == 2
    connection.close()