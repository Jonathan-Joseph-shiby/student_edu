from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from typing import Any, Callable

from ..config import get_settings
from .analysis import skill_detail, skill_rows, source_jobs


def ensure_admin_tables(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS course_outlines (
            outline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
            course_title TEXT NOT NULL,
            outline_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_course_outline_skill ON course_outlines(skill_id, created_at DESC);
    """)


def dashboard_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    gaps = skill_rows(connection, gaps_only=True)
    demand = skill_rows(connection)
    top_demand = max(demand, key=lambda row: (row["analyzed_job_count"], row["demand_score"]), default=None)
    top_gap = gaps[0] if gaps else None
    last = connection.execute("SELECT MAX(calculated_at) FROM skill_gap_analysis").fetchone()[0]
    return {
        "total_job_postings_analyzed": connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0],
        "total_canonical_skills": connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
        "total_curriculum_courses": connection.execute("SELECT COUNT(*) FROM curricula").fetchone()[0],
        "total_students": connection.execute("SELECT COUNT(*) FROM students").fetchone()[0],
        "total_recruiters": connection.execute("SELECT COUNT(*) FROM users WHERE role = 'recruiter'").fetchone()[0],
        "identified_skill_gaps": len(gaps),
        "top_demanded_skill": dict(top_demand) if top_demand else None,
        "highest_priority_gap": dict(top_gap) if top_gap else None,
        "last_analysis_at": last,
    }


def dashboard_rows(connection: sqlite3.Connection, minimum_demand: float = 0.0, search: str | None = None, maximum_coverage: float | None = None) -> list[sqlite3.Row]:
    rows = skill_rows(connection)
    return [row for row in rows if row["demand_score"] >= minimum_demand and (not search or search.casefold() in row["canonical_name"].casefold()) and (maximum_coverage is None or row["curriculum_coverage"] <= maximum_coverage)]


def drilldown(connection: sqlite3.Connection, skill_id: int) -> dict[str, Any] | None:
    detail = skill_detail(connection, skill_id)
    if detail is None:
        return None
    jobs = source_jobs(connection, skill_id)
    courses = connection.execute(
        """SELECT m.mapping_id, m.course_id, m.course_code, m.course_title, c.university,
                  c.state, c.semester, m.observed_skill, m.coverage, m.gap_analysis
           FROM curriculum_skill_observations m JOIN curricula c ON c.curriculum_id = m.course_id
           WHERE m.canonical_skill_id = ? ORDER BY m.course_id""", (skill_id,)
    ).fetchall()
    observations = connection.execute(
        "SELECT raw_skill, status, confidence, matching_method FROM skill_normalization_cache WHERE canonical_skill_id = ? OR status <> 'normalized' AND raw_skill IN (SELECT raw_skill FROM job_skill_observations WHERE canonical_skill_id IS NULL)",
        (skill_id,),
    ).fetchall()
    return {"skill": dict(detail), "source_job_count": len(jobs), "source_jobs": [dict(row) for row in jobs], "curriculum_courses": [dict(row) for row in courses], "skill_observations": [dict(row) for row in observations]}


def trends(connection: sqlite3.Connection) -> dict[str, Any]:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(job_postings)")}
    if "posting_date" not in columns:
        return {"available": False, "reason": "Posting-date data is insufficient for reliable trend analysis."}
    populated = connection.execute("SELECT COUNT(*) FROM job_postings WHERE posting_date IS NOT NULL AND posting_date <> ''").fetchone()[0]
    if populated < 2:
        return {"available": False, "reason": "Posting-date data is insufficient for reliable trend analysis."}
    return {"available": False, "reason": "Trend aggregation is unavailable for the current schema."}


def validate_outline(payload: object, skill_name: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("AI output must be a JSON object")
    required = ["course_title", "target_skill", "rationale", "target_audience", "prerequisites", "learning_objectives", "modules", "practical_activities", "assessment_strategy", "expected_outcomes", "recommended_resources"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"AI output missing fields: {', '.join(missing)}")
    if str(payload["target_skill"]).casefold() != skill_name.casefold():
        raise ValueError("AI target skill does not match selected canonical skill")
    if not isinstance(payload["modules"], list) or not payload["modules"]:
        raise ValueError("AI modules must be a non-empty list")
    if not isinstance(payload["learning_objectives"], list) or not payload["learning_objectives"]:
        raise ValueError("AI learning_objectives must be a non-empty list")
    resources = payload["recommended_resources"]
    if not isinstance(resources, list):
        raise ValueError("AI recommended_resources must be a list")
    allowed_resource_ids = {item["resource_id"] for item in evidence["resources"]}
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("resource_id") not in allowed_resource_ids:
            raise ValueError("AI output references an unavailable learning resource")
    return payload


def evidence_for_skill(connection: sqlite3.Connection, skill_id: int) -> dict[str, Any]:
    detail = drilldown(connection, skill_id)
    if detail is None:
        raise ValueError("Skill analysis not found")
    resources = [dict(row) for row in connection.execute("SELECT resource_id, resource_name, platform, url, level, type FROM learning_resources WHERE canonical_skill_id = ?", (skill_id,))]
    return {"skill": detail["skill"], "source_job_ids": [row["job_id"] for row in detail["source_jobs"]], "curriculum_mapping_ids": [row["mapping_id"] for row in detail["curriculum_courses"]], "resources": resources}


def anthropic_provider(context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("AI course generation is not configured.")
    request_body = {
        "model": settings.anthropic_model,
        "max_tokens": 1800,
        "temperature": 0,
        "system": "Return only valid JSON. Use only supplied project evidence. Do not invent job postings, curriculum courses, learning-resource URLs, or official approvals. Distinguish evidence from recommendations.",
        "messages": [{"role": "user", "content": json.dumps(context)}],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"AI course generation failed: {exc}") from exc
    content = payload.get("content", [])
    text = next((item.get("text") for item in content if item.get("type") == "text"), None)
    if not text:
        raise ValueError("AI provider returned no text content")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI provider returned malformed JSON") from exc


def generate_outline(connection: sqlite3.Connection, skill_id: int, title_preference: str | None = None, audience: str | None = None, duration: str | None = None, provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    ensure_admin_tables(connection)
    detail = skill_detail(connection, skill_id)
    if detail is None:
        raise ValueError("Skill analysis not found")
    evidence = evidence_for_skill(connection, skill_id)
    if provider is None and not get_settings().anthropic_api_key:
        return {"available": False, "reason": "AI course generation is not configured.", "evidence": evidence}
    if provider is None:
        provider = anthropic_provider
    context = {"evidence": evidence, "course_title_preference": title_preference, "target_audience": audience, "duration": duration, "instruction": "Use only supplied project evidence. Do not invent postings, courses, URLs, or official approvals. Distinguish evidence from recommendations. Return JSON only."}
    payload = validate_outline(provider(context), detail["canonical_name"], evidence)
    cursor = connection.execute("INSERT INTO course_outlines(skill_id, course_title, outline_json, evidence_json, provider, model) VALUES (?, ?, ?, ?, ?, ?)", (skill_id, payload["course_title"], json.dumps(payload), json.dumps(evidence), "configured-provider", None))
    connection.commit()
    return {"available": True, "outline_id": cursor.lastrowid, "outline": payload, "evidence": evidence}


def outline_history(connection: sqlite3.Connection, skill_id: int | None = None) -> list[dict[str, Any]]:
    ensure_admin_tables(connection)
    where = "WHERE o.skill_id = ?" if skill_id is not None else ""
    args = (skill_id,) if skill_id is not None else ()
    return [dict(row) | {"outline": json.loads(row["outline_json"]), "evidence": json.loads(row["evidence_json"])} for row in connection.execute(f"SELECT o.outline_id, o.skill_id, s.canonical_name AS skill, o.course_title, o.outline_json, o.evidence_json, o.provider, o.model, o.created_at FROM course_outlines o JOIN skills s ON s.skill_id=o.skill_id {where} ORDER BY o.created_at DESC", args)]