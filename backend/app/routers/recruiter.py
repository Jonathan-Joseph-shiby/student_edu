from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..database import get_db
from ..dependencies import require_role
from ..schemas import RecruiterJobRequest, RecruiterJobUpdate
from ..services.recruiter import (create_job, ensure_recruiter_tables, job, match_candidates,
                                  update_job)


router = APIRouter(prefix="/recruiter", tags=["recruiter"])


def owner(user: sqlite3.Row, connection: sqlite3.Connection) -> int:
    ensure_recruiter_tables(connection)
    return int(user["id"])


@router.get("/profile")
def profile(user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    owner(user, connection)
    return {"user_id": user["id"], "email": user["email"], "role": user["role"], "company": None, "company_note": "Imported jobs and companies are not defensibly linked; recruiter-created openings use display-only company information."}


@router.get("/jobs")
def jobs(user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    owner_id = owner(user, connection)
    rows = connection.execute("SELECT * FROM recruiter_jobs WHERE recruiter_user_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
    return {"items": [job(connection, owner_id, row["job_id"]) for row in rows], "total": len(rows)}


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create(payload: RecruiterJobRequest, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    owner_id = owner(user, connection)
    try:
        return create_job(connection, owner_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    result = job(connection, owner(user, connection), job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job opening not found")
    return result


@router.put("/jobs/{job_id}")
def edit_job(job_id: str, payload: RecruiterJobUpdate, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    try:
        result = update_job(connection, owner(user, connection), job_id, {key: value for key, value in payload.model_dump().items() if value is not None})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Job opening not found")
    return result


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    owner_id = owner(user, connection)
    if connection.execute("DELETE FROM recruiter_jobs WHERE job_id = ? AND recruiter_user_id = ?", (job_id, owner_id)).rowcount == 0:
        raise HTTPException(status_code=404, detail="Job opening not found")
    connection.commit()
    return {"status": "deleted", "job_id": job_id}


@router.get("/jobs/{job_id}/matches")
def matches(job_id: str, target_role: str | None = None, skill_id: int | None = None, min_match_score: float | None = Query(default=None, ge=0, le=100), min_readiness: float | None = Query(default=None, ge=0, le=100), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    try:
        rows = match_candidates(connection, owner(user, connection), job_id, target_role, skill_id, min_match_score, min_readiness)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "page": page, "page_size": page_size, "total": len(rows), "formula": "required_match, plus 20% preferred_match when preferred skills exist"}


@router.get("/jobs/{job_id}/matches/{student_id}")
def match_detail(job_id: str, student_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = match_candidates(connection, owner(user, connection), job_id)
    result = next((row for row in rows if row["student_id"] == student_id), None)
    if result is None:
        raise HTTPException(status_code=404, detail="Candidate match not found")
    return result


@router.post("/jobs/{job_id}/shortlist/{student_id}")
def shortlist(job_id: str, student_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    owner_id = owner(user, connection)
    if job(connection, owner_id, job_id) is None or connection.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Job or student not found")
    connection.execute("INSERT OR IGNORE INTO recruiter_shortlists(job_id, recruiter_user_id, student_id) VALUES (?, ?, ?)", (job_id, owner_id, student_id))
    connection.commit()
    return {"status": "shortlisted", "job_id": job_id, "student_id": student_id}


@router.delete("/jobs/{job_id}/shortlist/{student_id}")
def remove_shortlist(job_id: str, student_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    owner_id = owner(user, connection)
    deleted = connection.execute("DELETE FROM recruiter_shortlists WHERE job_id = ? AND recruiter_user_id = ? AND student_id = ?", (job_id, owner_id, student_id)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Shortlist entry not found")
    connection.commit()
    return {"status": "removed", "job_id": job_id, "student_id": student_id}


@router.get("/jobs/{job_id}/shortlist")
def get_shortlist(job_id: str, user: sqlite3.Row = Depends(require_role("recruiter")), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    owner_id = owner(user, connection)
    if job(connection, owner_id, job_id) is None:
        raise HTTPException(status_code=404, detail="Job opening not found")
    rows = connection.execute("SELECT s.student_id, s.name, s.degree, s.department, s.year, r.created_at FROM recruiter_shortlists r JOIN students s ON s.student_id=r.student_id WHERE r.job_id = ? AND r.recruiter_user_id = ? ORDER BY r.created_at", (job_id, owner_id)).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}