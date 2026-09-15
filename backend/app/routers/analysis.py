from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..services.analysis import recompute_analysis, skill_detail, skill_rows, source_jobs, unresolved_rows


router = APIRouter(tags=["analysis"])


def as_dict(row: sqlite3.Row) -> dict[str, object]:
    return dict(row)


@router.get("/skills")
def skills(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = connection.execute("SELECT skill_id, canonical_name, category FROM skills ORDER BY canonical_name").fetchall()
    return {"items": [as_dict(row) for row in rows], "total": len(rows)}


@router.get("/skills/{skill_id}")
def skill(skill_id: int, connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    row = skill_detail(connection, skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Skill analysis not found; run admin recomputation")
    return as_dict(row)


@router.get("/industry/demand")
def demand(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = skill_rows(connection)
    return {"items": [as_dict(row) for row in rows], "total": len(rows)}


@router.get("/industry/demand/{skill_id}")
def skill_demand(skill_id: int, connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    row = skill_detail(connection, skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Skill demand not found")
    return as_dict(row)


@router.get("/curriculum/coverage")
def coverage(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = skill_rows(connection)
    return {"items": [as_dict(row) for row in rows], "total": len(rows)}


@router.get("/curriculum/gaps")
def gaps(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    rows = skill_rows(connection, gaps_only=True)
    return {"items": [as_dict(row) for row in rows], "total": len(rows)}


@router.get("/analysis/skill-gaps")
def skill_gaps(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), connection: sqlite3.Connection = Depends(get_db), _: sqlite3.Row = Depends(get_current_user)) -> dict[str, object]:
    rows = skill_rows(connection, gaps_only=True)
    start = (page - 1) * page_size
    return {"items": [as_dict(row) for row in rows[start:start + page_size]], "page": page, "page_size": page_size, "total": len(rows)}


@router.get("/analysis/skill-gaps/{skill_id}")
def gap_detail(skill_id: int, connection: sqlite3.Connection = Depends(get_db), _: sqlite3.Row = Depends(get_current_user)) -> dict[str, object]:
    row = skill_detail(connection, skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Skill gap not found")
    return as_dict(row)


@router.get("/analysis/skill-gaps/{skill_id}/sources")
def gap_sources(skill_id: int, connection: sqlite3.Connection = Depends(get_db), _: sqlite3.Row = Depends(get_current_user)) -> dict[str, object]:
    if skill_detail(connection, skill_id) is None:
        raise HTTPException(status_code=404, detail="Skill gap not found")
    rows = source_jobs(connection, skill_id)
    return {"skill_id": skill_id, "items": [as_dict(row) for row in rows], "total": len(rows)}


@router.post("/admin/analysis/recompute")
def recompute(connection: sqlite3.Connection = Depends(get_db), _: sqlite3.Row = Depends(require_role("admin"))) -> dict[str, object]:
    return {"status": "recomputed", "results": recompute_analysis(connection)}


@router.get("/admin/skills/unresolved")
def unresolved(connection: sqlite3.Connection = Depends(get_db), _: sqlite3.Row = Depends(require_role("admin"))) -> dict[str, object]:
    rows = unresolved_rows(connection)
    items = []
    for row in rows:
        item = as_dict(row)
        item["proposed_canonical_mapping"] = None
        item["reason"] = "No approved canonical mapping"
        items.append(item)
    return {"items": items, "total": len(items)}