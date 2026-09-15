from __future__ import annotations

import os

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import get_db
from .routers import admin, analysis, auth, recruiter, student, try_it, verification


app = FastAPI(title="SkillBridge API", version="1.0.0")
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api/v1")


@api.get("/health")
def health(connection=Depends(get_db)) -> dict[str, object]:
    try:
        connection.execute("SELECT 1").fetchone()
        connection.execute("SELECT 1 FROM users LIMIT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok", "backend": "operational", "database": "operational"}


api.include_router(auth.router)
api.include_router(verification.router)
api.include_router(analysis.router)
api.include_router(student.router)
api.include_router(recruiter.router)
api.include_router(admin.router)
api.include_router(try_it.router)
app.include_router(api)