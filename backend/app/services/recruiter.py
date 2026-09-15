from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from .normalization import ensure_tables, normalize_skill
from .student import current_scores, readiness


def ensure_recruiter_tables(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS recruiter_jobs (
            job_id TEXT PRIMARY KEY, recruiter_user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
            description TEXT NOT NULL, location TEXT NOT NULL, company_display_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('open', 'closed', 'draft')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recruiter_job_skills (
            job_skill_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES recruiter_jobs(job_id) ON DELETE CASCADE,
            skill_id INTEGER NOT NULL REFERENCES skills(skill_id), raw_skill TEXT NOT NULL,
            requirement TEXT NOT NULL CHECK (requirement IN ('required', 'preferred')), UNIQUE(job_id, skill_id, requirement)
        );
        CREATE TABLE IF NOT EXISTS recruiter_shortlists (
            job_id TEXT NOT NULL REFERENCES recruiter_jobs(job_id) ON DELETE CASCADE,
            recruiter_user_id INTEGER NOT NULL REFERENCES users(id), student_id TEXT NOT NULL REFERENCES students(student_id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(job_id, student_id)
        );
        CREATE INDEX IF NOT EXISTS idx_recruiter_job_owner ON recruiter_jobs(recruiter_user_id);
        CREATE INDEX IF NOT EXISTS idx_recruiter_job_skill ON recruiter_job_skills(job_id, requirement);
    """)


def normalize_job_skills(connection: sqlite3.Connection, names: list[str]) -> list[dict[str, Any]]:
    results = []
    seen = set()
    seen_canonical = set()
    for name in names:
        raw = name.strip()
        if not raw or raw.casefold() in seen:
            continue
        seen.add(raw.casefold())
        result = normalize_skill(connection, raw)
        if result.status != "normalized" or result.canonical_skill_id is None:
            raise ValueError(f"Skill requires review before use: {raw}")
        if result.canonical_skill_id in seen_canonical:
            continue
        seen_canonical.add(result.canonical_skill_id)
        results.append({"raw_skill": raw, "skill_id": result.canonical_skill_id, "canonical_skill": result.canonical_skill})
    return results


def create_job(connection: sqlite3.Connection, owner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_recruiter_tables(connection)
    required = normalize_job_skills(connection, payload["required_skills"])
    preferred = normalize_job_skills(connection, payload.get("preferred_skills", []))
    required_ids = {item["skill_id"] for item in required}
    preferred = [item for item in preferred if item["skill_id"] not in required_ids]
    job_id = f"RJOB-{uuid.uuid4().hex[:12].upper()}"
    connection.execute("INSERT INTO recruiter_jobs(job_id, recruiter_user_id, title, description, location, company_display_name, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (job_id, owner_id, payload["title"], payload["description"], payload["location"], payload["company_display_name"], payload.get("status", "draft")))
    connection.executemany("INSERT INTO recruiter_job_skills(job_id, skill_id, raw_skill, requirement) VALUES (?, ?, ?, 'required')", [(job_id, item["skill_id"], item["raw_skill"]) for item in required])
    connection.executemany("INSERT INTO recruiter_job_skills(job_id, skill_id, raw_skill, requirement) VALUES (?, ?, ?, 'preferred')", [(job_id, item["skill_id"], item["raw_skill"]) for item in preferred])
    connection.commit()
    return job(connection, owner_id, job_id)


def job(connection: sqlite3.Connection, owner_id: int, job_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM recruiter_jobs WHERE job_id = ? AND recruiter_user_id = ?", (job_id, owner_id)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["required_skills"] = [dict(item) for item in connection.execute("SELECT skill_id, raw_skill, requirement FROM recruiter_job_skills WHERE job_id = ? AND requirement = 'required' ORDER BY skill_id", (job_id,))]
    result["preferred_skills"] = [dict(item) for item in connection.execute("SELECT skill_id, raw_skill, requirement FROM recruiter_job_skills WHERE job_id = ? AND requirement = 'preferred' ORDER BY skill_id", (job_id,))]
    return result


def update_job(connection: sqlite3.Connection, owner_id: int, job_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    existing = job(connection, owner_id, job_id)
    if existing is None:
        return None
    scalar = {key: value for key, value in payload.items() if key in {"title", "description", "location", "company_display_name", "status"} and value is not None}
    if scalar:
        connection.execute(f"UPDATE recruiter_jobs SET {', '.join(f'{key} = ?' for key in scalar)}, updated_at=CURRENT_TIMESTAMP WHERE job_id = ? AND recruiter_user_id = ?", [*scalar.values(), job_id, owner_id])
    if payload.get("required_skills") is not None or payload.get("preferred_skills") is not None:
        required = normalize_job_skills(connection, payload.get("required_skills", [item["raw_skill"] for item in existing["required_skills"]]))
        preferred = normalize_job_skills(connection, payload.get("preferred_skills", [item["raw_skill"] for item in existing["preferred_skills"]]))
        connection.execute("DELETE FROM recruiter_job_skills WHERE job_id = ?", (job_id,))
        required_ids = {item["skill_id"] for item in required}
        preferred = [item for item in preferred if item["skill_id"] not in required_ids]
        connection.executemany("INSERT INTO recruiter_job_skills(job_id, skill_id, raw_skill, requirement) VALUES (?, ?, ?, 'required')", [(job_id, item["skill_id"], item["raw_skill"]) for item in required])
        connection.executemany("INSERT INTO recruiter_job_skills(job_id, skill_id, raw_skill, requirement) VALUES (?, ?, ?, 'preferred')", [(job_id, item["skill_id"], item["raw_skill"]) for item in preferred])
    connection.commit()
    return job(connection, owner_id, job_id)


def _score_for_candidate(connection: sqlite3.Connection, student_id: str, skill_id: int) -> float:
    return float(current_scores(connection, student_id).get(skill_id, 0.0))


def match_candidates(connection: sqlite3.Connection, owner_id: int, job_id: str, target_role: str | None = None, skill_id: int | None = None, min_match_score: float | None = None, min_readiness: float | None = None) -> list[dict[str, Any]]:
    opening = job(connection, owner_id, job_id)
    if opening is None:
        raise ValueError("Job opening not found")
    required = connection.execute("SELECT skill_id, raw_skill FROM recruiter_job_skills WHERE job_id = ? AND requirement = 'required' ORDER BY skill_id", (job_id,)).fetchall()
    preferred = connection.execute("SELECT skill_id, raw_skill FROM recruiter_job_skills WHERE job_id = ? AND requirement = 'preferred' ORDER BY skill_id", (job_id,)).fetchall()
    candidates = connection.execute("SELECT student_id, name, degree, department, year FROM students ORDER BY student_id").fetchall()
    results = []
    for candidate in candidates:
        student_id = candidate["student_id"]
        target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
        if target_role and (target is None or target[0] != target_role):
            continue
        if skill_id is not None and not any(row["skill_id"] == skill_id for row in (*required, *preferred)):
            continue
        score_map = current_scores(connection, student_id)
        required_details = [{"skill_id": row["skill_id"], "skill": connection.execute("SELECT canonical_name FROM skills WHERE skill_id = ?", (row["skill_id"],)).fetchone()[0], "score": float(score_map.get(row["skill_id"], 0.0))} for row in required]
        preferred_details = [{"skill_id": row["skill_id"], "skill": connection.execute("SELECT canonical_name FROM skills WHERE skill_id = ?", (row["skill_id"],)).fetchone()[0], "score": float(score_map.get(row["skill_id"], 0.0))} for row in preferred]
        required_match = sum(item["score"] for item in required_details) / len(required_details) if required_details else 0.0
        preferred_match = sum(item["score"] for item in preferred_details) / len(preferred_details) if preferred_details else None
        final_match = required_match if preferred_match is None else 0.8 * required_match + 0.2 * preferred_match
        coverage = sum(item["score"] >= 70 for item in required_details) / len(required_details) if required_details else 0.0
        readiness_score = readiness(connection, student_id)
        if min_match_score is not None and final_match < min_match_score:
            continue
        if min_readiness is not None and (readiness_score is None or readiness_score < min_readiness):
            continue
        results.append({"student_id": student_id, "name": candidate["name"], "degree": candidate["degree"], "department": candidate["department"], "year": candidate["year"], "target_role": target[0] if target else None, "match_score": round(final_match, 2), "required_match": round(required_match, 2), "preferred_match": round(preferred_match, 2) if preferred_match is not None else None, "required_skill_coverage": round(coverage, 4), "readiness_score": readiness_score, "strong_matches": [item for item in required_details if item["score"] >= 70], "skill_gaps": [item for item in required_details if item["score"] < 70], "preferred_skills": preferred_details})
    return sorted(results, key=lambda item: (-item["match_score"], -item["required_skill_coverage"], -(item["readiness_score"] or 0), item["student_id"]))
