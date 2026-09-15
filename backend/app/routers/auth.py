from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from ..security import create_access_token, hash_password, verify_password
from ..services.student import create_student_profile


router = APIRouter(prefix="/auth", tags=["authentication"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def user_response(row: sqlite3.Row) -> UserResponse:
    return UserResponse(id=row["id"], email=row["email"], role=row["role"], is_active=bool(row["is_active"]), student_id=row["student_id"], created_at=row["created_at"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, connection: sqlite3.Connection = Depends(get_db)) -> UserResponse:
    email = payload.email.strip().casefold()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="A valid email is required")
    student_id = payload.student_id
    if payload.role == "student" and student_id:
        student = connection.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if student is None:
            raise HTTPException(status_code=400, detail="student_id does not reference an existing student")
    try:
        if payload.role == "student" and student_id is None:
            connection.execute("BEGIN IMMEDIATE")
            student_id = create_student_profile(connection, email, payload.model_dump())
        cursor = connection.execute(
            "INSERT INTO users(email, password_hash, role, student_id) VALUES (?, ?, ?, ?)",
            (email, hash_password(payload.password), payload.role, student_id),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered") from None
    except Exception:
        connection.rollback()
        raise
    row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return user_response(row)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, connection: sqlite3.Connection = Depends(get_db)) -> TokenResponse:
    row = connection.execute("SELECT * FROM users WHERE email = ?", (payload.email.strip().casefold(),)).fetchone()
    if row is None or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(row["id"], row["role"]), user=user_response(row))


@router.get("/me", response_model=UserResponse)
def me(user: sqlite3.Row = Depends(get_current_user)) -> UserResponse:
    return user_response(user)