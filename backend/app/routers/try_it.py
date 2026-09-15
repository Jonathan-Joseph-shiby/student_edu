from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import TryItRequest
from ..services.try_it import analyze


router = APIRouter(prefix="/try-it", tags=["try-it-live"])


@router.post("/{mode}")
def try_it(mode: str, payload: TryItRequest, user: sqlite3.Row = Depends(get_current_user), connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    if mode not in {"job", "resume", "syllabus"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Try It Live mode not found")
    return analyze(connection, mode, payload.text, payload.target_role)