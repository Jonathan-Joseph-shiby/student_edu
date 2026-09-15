from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["JWT_SECRET_KEY"] = "test-only-secret"
os.environ["JWT_ALGORITHM"] = "HS256"

from backend.app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "test.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    connection.execute("INSERT INTO students(student_id, name, state, degree, department, year, semester, skills, experience, certifications, assessment_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("S001", "Test Student", "Delhi", "B.Tech", "Computer Science", 3, 6, "Python", "None", "None", 80))
    connection.commit()
    connection.close()
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(database_path))
    with TestClient(app) as test_client:
        yield test_client


def register(client: TestClient, email: str, role: str = "student") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role, "student_id": "S001" if role == "student" else None})
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str = "StrongPassword123!") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "backend": "operational", "database": "operational"}


def test_registration_and_duplicate_email(client: TestClient) -> None:
    user = register(client, "student@example.com")
    assert user["role"] == "student"
    assert "password_hash" not in user
    duplicate = client.post("/api/v1/auth/register", json={"email": "STUDENT@example.com", "password": "StrongPassword123!", "role": "student"})
    assert duplicate.status_code == 409


def test_invalid_role_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": "bad@example.com", "password": "StrongPassword123!", "role": "owner"})
    assert response.status_code == 422


def test_login_and_me(client: TestClient) -> None:
    register(client, "student@example.com")
    token = login(client, "student@example.com")
    response = client.get("/api/v1/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"


def test_wrong_password_and_missing_token(client: TestClient) -> None:
    register(client, "student@example.com")
    wrong = client.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "wrong-password"})
    assert wrong.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_role_protected_routes(client: TestClient) -> None:
    register(client, "admin@example.com", "admin")
    register(client, "recruiter@example.com", "recruiter")
    register(client, "student@example.com", "student")
    admin_token = login(client, "admin@example.com")
    recruiter_token = login(client, "recruiter@example.com")
    student_token = login(client, "student@example.com")
    assert client.get("/api/v1/admin/test", headers=auth(admin_token)).status_code == 200
    assert client.get("/api/v1/admin/test", headers=auth(student_token)).status_code == 403
    assert client.get("/api/v1/recruiter/test", headers=auth(recruiter_token)).status_code == 200
    assert client.get("/api/v1/student/test", headers=auth(student_token)).status_code == 200
    assert client.get("/api/v1/student/test", headers=auth(admin_token)).status_code == 403


def test_invalid_and_expired_tokens_rejected(client: TestClient) -> None:
    invalid = client.get("/api/v1/auth/me", headers=auth("not-a-jwt"))
    assert invalid.status_code == 401
    expired = jwt.encode({"sub": "1", "role": "student", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, "test-only-secret", algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers=auth(expired)).status_code == 401