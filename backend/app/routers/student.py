from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import AssessmentSubmitRequest, ProgressRequest, StudentProfileUpdate, TargetRoleRequest
from ..services.student import (ensure_student_tables, personal_gap, readiness, recommendations, roadmap,
                                role_skills, roles, student_id_for_user, submit_assessment)


router = APIRouter(prefix="/student", tags=["student"])


def student_context(user: sqlite3.Row, connection: sqlite3.Connection) -> str:
    try:
        student_id = student_id_for_user(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    ensure_student_tables(connection)
    if connection.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Linked student profile not found")
    return student_id


@router.get("/profile")
def profile(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    row = connection.execute("SELECT student_id, name, state, degree, department, year, semester, skills, experience, certifications FROM students WHERE student_id = ?", (student_id,)).fetchone()
    result = dict(row)
    result["email"] = user["email"]
    target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
    result["target_role"] = target[0] if target else None
    return result


@router.put("/profile")
def update_profile(payload: StudentProfileUpdate, user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if updates:
        connection.execute(f"UPDATE students SET {', '.join(f'{key} = ?' for key in updates)} WHERE student_id = ?", [*updates.values(), student_id])
        connection.commit()
    return profile(user, connection)


@router.get("/roles")
def available_roles(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_context(user, connection)
    return {"items": [dict(row) for row in roles(connection)]}


@router.put("/target-role")
def target_role(payload: TargetRoleRequest, user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    role = payload.target_role.strip()
    if connection.execute("SELECT 1 FROM job_postings WHERE job_title = ?", (role,)).fetchone() is None:
        raise HTTPException(status_code=400, detail="Target role must exist in the current job dataset")
    connection.execute("INSERT INTO student_target_roles(student_id, target_role) VALUES (?, ?) ON CONFLICT(student_id) DO UPDATE SET target_role=excluded.target_role, updated_at=CURRENT_TIMESTAMP", (student_id, role))
    connection.commit()
    return {"student_id": student_id, "target_role": role, "required_skills": [dict(row) for row in role_skills(connection, role)]}


@router.get("/assessment")
def assessment_questions(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_context(user, connection)
    rows = connection.execute("SELECT question_id, observed_skill, difficulty, question FROM assessment_questions ORDER BY question_id").fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.post("/assessment/submit")
def assessment_submit(payload: AssessmentSubmitRequest, user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    try:
        return submit_assessment(connection, student_id, [answer.model_dump() for answer in payload.answers])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/assessment/latest")
def assessment_latest(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object] | None:
    student_id = student_context(user, connection)
    attempt = connection.execute("SELECT attempt_id, version, total_score, submitted_at FROM assessment_attempts WHERE student_id = ? ORDER BY version DESC LIMIT 1", (student_id,)).fetchone()
    if attempt is None:
        return None
    result = dict(attempt)
    result["skill_scores"] = [dict(row) for row in connection.execute("SELECT x.skill_id, s.canonical_name AS skill, x.score, x.level FROM student_skill_scores x JOIN skills s ON s.skill_id=x.skill_id WHERE x.attempt_id = ?", (attempt["attempt_id"],))]
    return result


@router.get("/assessment/history")
def assessment_history(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    rows = connection.execute("SELECT attempt_id, version, total_score, submitted_at FROM assessment_attempts WHERE student_id = ? ORDER BY version", (student_id,)).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.get("/skill-gap")
def skill_gap(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    return personal_gap(connection, student_context(user, connection))


@router.get("/readiness")
def student_readiness(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
    return {"label": "SkillBridge Readiness Score", "target_role": target[0] if target else None, "score": readiness(connection, student_id)}


@router.get("/recommendations")
def student_recommendations(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    return {"items": recommendations(connection, student_context(user, connection))}


@router.get("/roadmap")
def student_roadmap(user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    return {"items": roadmap(connection, student_context(user, connection))}


@router.post("/progress")
def progress(payload: ProgressRequest, user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    student_id = student_context(user, connection)
    if connection.execute("SELECT 1 FROM skills WHERE skill_id = ?", (payload.skill_id,)).fetchone() is None:
        raise HTTPException(status_code=400, detail="Unknown skill_id")
    if payload.resource_id is not None and connection.execute("SELECT 1 FROM learning_resources WHERE resource_id = ?", (payload.resource_id,)).fetchone() is None:
        raise HTTPException(status_code=400, detail="Unknown resource_id")
    connection.execute("INSERT INTO student_progress(student_id, skill_id, resource_id, status, week_number) VALUES (?, ?, ?, ?, ?) ON CONFLICT(student_id, skill_id, resource_id) DO UPDATE SET status=excluded.status, week_number=excluded.week_number, updated_at=CURRENT_TIMESTAMP", (student_id, payload.skill_id, payload.resource_id, payload.status, payload.week_number))
    connection.commit()
    return {"status": "saved", "student_id": student_id, **payload.model_dump()}