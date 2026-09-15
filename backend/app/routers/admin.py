from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..dependencies import require_role
from ..schemas import CourseOutlineRequest
from ..services.admin import (dashboard_rows, dashboard_summary, drilldown, ensure_admin_tables,
                              generate_outline, outline_history, trends)
from ..services.student import current_scores, personal_gap, readiness, roadmap


router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


def student_detail(connection: sqlite3.Connection, student_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT student_id, name, state, degree, department, year, semester, skills, experience, certifications, assessment_score FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if row is None:
        return None
    target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
    target_role = target[0] if target else None
    scores = current_scores(connection, student_id)
    demonstrated = [dict(item) | {"score": scores.get(item["skill_id"], 0.0)} for item in connection.execute("SELECT skill_id, canonical_name AS skill FROM skills WHERE skill_id IN ({})".format(",".join("?" for _ in scores)) if scores else "SELECT skill_id, canonical_name AS skill FROM skills WHERE 0", tuple(scores))]
    latest = connection.execute("SELECT attempt_id, version, total_score, submitted_at FROM assessment_attempts WHERE student_id = ? ORDER BY version DESC LIMIT 1", (student_id,)).fetchone()
    latest_scores = []
    if latest:
        latest_scores = [dict(item) for item in connection.execute("SELECT x.skill_id, s.canonical_name AS skill, x.score, x.level FROM student_skill_scores x JOIN skills s ON s.skill_id = x.skill_id WHERE x.attempt_id = ?", (latest["attempt_id"],))]
    gap = personal_gap(connection, student_id)
    return {"profile": dict(row), "target_role": target_role, "demonstrated_skills": demonstrated, "latest_assessment": dict(latest) if latest else None, "latest_scores": latest_scores, "skill_gaps": gap["items"], "readiness": readiness(connection, student_id), "roadmap": roadmap(connection, student_id), "progress": [dict(item) for item in connection.execute("SELECT skill_id, resource_id, status, week_number, updated_at FROM student_progress WHERE student_id = ? ORDER BY week_number", (student_id,))]}


@router.get("/students")
def students(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = connection.execute("SELECT s.student_id, s.name, s.degree, s.department, s.year, r.target_role FROM students s LEFT JOIN student_target_roles r ON r.student_id = s.student_id ORDER BY s.student_id").fetchall()
    items = []
    for row in rows:
        item = dict(row)
        gap = personal_gap(connection, row["student_id"])
        item["readiness"] = readiness(connection, row["student_id"])
        item["skill_gap_count"] = sum(gap_item["gap_score"] > 0 for gap_item in gap["items"])
        items.append(item)
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "page": page, "page_size": page_size, "total": len(items)}


@router.get("/students/{student_id}")
def student(student_id: str, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    result = student_detail(connection, student_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return result


def admin_db(user: sqlite3.Row, connection: sqlite3.Connection) -> sqlite3.Row:
    ensure_admin_tables(connection)
    return user


@router.get("/dashboard/summary")
def summary(user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    return dashboard_summary(connection)


@router.get("/dashboard/industry-demand")
def industry_demand(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), minimum_demand: float = Query(0, ge=0, le=1), search: str | None = None, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    rows = dashboard_rows(connection, minimum_demand=minimum_demand, search=search)
    start = (page - 1) * page_size
    items = []
    for rank, row in enumerate(rows, 1):
        item = dict(row)
        item["rank"] = rank
        item["source_job_count"] = row["analyzed_job_count"]
        items.append(item)
    return {"items": items[start:start + page_size], "page": page, "page_size": page_size, "total": len(items)}


@router.get("/dashboard/industry-demand/{skill_id}")
def industry_demand_detail(skill_id: int, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    result = drilldown(connection, skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Skill analysis not found")
    return result["skill"] | {"source_job_count": result["source_job_count"]}


@router.get("/dashboard/curriculum-coverage")
def curriculum_coverage(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), minimum_demand: float = Query(0, ge=0, le=1), maximum_coverage: float | None = Query(default=None, ge=0, le=1), user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    rows = dashboard_rows(connection, minimum_demand=minimum_demand, maximum_coverage=maximum_coverage)
    start = (page - 1) * page_size
    return {"items": [dict(row) for row in rows[start:start + page_size]], "page": page, "page_size": page_size, "total": len(rows)}


@router.get("/dashboard/skill-gaps")
def skill_gaps(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), minimum_demand: float = Query(0, ge=0, le=1), search: str | None = None, maximum_coverage: float | None = Query(default=None, ge=0, le=1), user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    rows = [row for row in dashboard_rows(connection, minimum_demand, search, maximum_coverage) if row["gap_status"] == "gap"]
    start = (page - 1) * page_size
    return {"items": [{"rank": start + index + 1, **dict(row)} for index, row in enumerate(rows[start:start + page_size])], "page": page, "page_size": page_size, "total": len(rows), "formula": "gap_score = demand_score * (1 - curriculum_coverage)"}


@router.get("/dashboard/skill-gaps/{skill_id}")
def skill_gap_detail(skill_id: int, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    result = drilldown(connection, skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Skill gap not found")
    return result


@router.get("/dashboard/trends")
def dashboard_trends(user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    return trends(connection)


@router.post("/course-outline/generate")
def course_outline(payload: CourseOutlineRequest, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    try:
        return generate_outline(connection, payload.skill_id, payload.course_title_preference, payload.target_audience, payload.duration)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/course-outline/history")
def course_outline_history(skill_id: int | None = None, user: sqlite3.Row = Depends(require_role("admin")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    admin_db(user, connection)
    items = outline_history(connection, skill_id)
    return {"items": items, "total": len(items)}