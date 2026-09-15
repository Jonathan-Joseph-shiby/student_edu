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
os.environ["JWT_SECRET_KEY"] = "phase3-test-secret"

from backend.app.main import app  # noqa: E402
from backend.app.services.analysis import recompute_analysis, skill_rows, source_jobs  # noqa: E402
from backend.app.services.normalization import normalize_skill  # noqa: E402


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "industrypulse.sqlite3"
    shutil.copy2(ROOT / "db" / "industrypulse.sqlite3", path)
    monkeypatch.setenv("INDUSTRYPULSE_DB_PATH", str(path))
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    recompute_analysis(connection)
    connection.close()
    return path


@pytest.fixture()
def client(database: Path) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def token(client: TestClient, email: str, role: str) -> str:
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPassword123!", "role": role})
    assert registered.status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_normalization_alias_and_unresolved_are_safe(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    assert normalize_skill(connection, "Excel").canonical_skill == "Microsoft Excel"
    assert normalize_skill(connection, "ReactJS").canonical_skill == "React"
    unresolved = normalize_skill(connection, "PostgreSQL")
    assert unresolved.status == "normalized" or unresolved.status == "unresolved"
    assert normalize_skill(connection, "TensorFlow").canonical_skill != "Machine Learning"
    connection.close()


def test_normalization_cache_reuses_result(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    first = normalize_skill(connection, "ReactJS")
    second = normalize_skill(connection, "ReactJS")
    assert first == second
    assert connection.execute("SELECT COUNT(*) FROM skill_normalization_cache WHERE raw_skill = 'ReactJS'").fetchone()[0] == 1
    connection.close()


def test_demand_counts_distinct_jobs_and_gap_ranking(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    rows = skill_rows(connection, gaps_only=True)
    assert rows == sorted(rows, key=lambda row: (-row["gap_score"], -row["demand_score"], row["canonical_name"]))
    python = connection.execute("SELECT skill_id FROM skills WHERE canonical_name = 'Python'").fetchone()[0]
    demand = connection.execute("SELECT analyzed_job_count FROM skill_gap_analysis WHERE skill_id = ?", (python,)).fetchone()[0]
    expected = connection.execute("SELECT COUNT(DISTINCT job_id) FROM job_skill_observations WHERE canonical_skill_id = ?", (python,)).fetchone()[0]
    assert demand == expected
    connection.close()


def test_traceability_returns_original_company_and_null_metadata(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    python = connection.execute("SELECT skill_id FROM skills WHERE canonical_name = 'Python'").fetchone()[0]
    sources = source_jobs(connection, python)
    assert sources
    assert sources[0]["source_company_name"]
    assert sources[0]["source_url"] is None
    assert sources[0]["posting_date"] is None
    connection.close()


def test_analysis_requires_auth_and_admin_recompute(client: TestClient) -> None:
    assert client.get("/api/v1/analysis/skill-gaps").status_code == 401
    student_token = token(client, "student.phase3@example.com", "student")
    admin_token = token(client, "admin.phase3@example.com", "admin")
    assert client.post("/api/v1/admin/analysis/recompute", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403
    response = client.post("/api/v1/admin/analysis/recompute", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["results"]["total_jobs"] == 20


def test_unresolved_report_is_admin_only(client: TestClient) -> None:
    student_token = token(client, "student.unresolved@example.com", "student")
    admin_token = token(client, "admin.unresolved@example.com", "admin")
    assert client.get("/api/v1/admin/skills/unresolved", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403
    response = client.get("/api/v1/admin/skills/unresolved", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["total"] > 0