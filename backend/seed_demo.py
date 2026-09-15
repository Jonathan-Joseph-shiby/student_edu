from __future__ import annotations

import os
import sqlite3

from app.config import get_settings
from app.security import hash_password


def seed(connection: sqlite3.Connection) -> None:
    accounts = [
        (os.getenv("DEMO_ADMIN_EMAIL", "admin.demo@industrypulse.local"), os.getenv("DEMO_ADMIN_PASSWORD", "change-this-admin-password"), "admin", None),
        (os.getenv("DEMO_RECRUITER_EMAIL", "recruiter.demo@industrypulse.local"), os.getenv("DEMO_RECRUITER_PASSWORD", "change-this-recruiter-password"), "recruiter", None),
        (os.getenv("DEMO_STUDENT_EMAIL", "student.demo@industrypulse.local"), os.getenv("DEMO_STUDENT_PASSWORD", "change-this-student-password"), "student", os.getenv("DEMO_STUDENT_ID", "S001")),
    ]
    for email, password, role, student_id in accounts:
        connection.execute(
            "INSERT INTO users(email, password_hash, role, student_id) VALUES (?, ?, ?, ?) ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash, role=excluded.role, student_id=excluded.student_id, is_active=1",
            (email.casefold(), hash_password(password), role, student_id),
        )
    connection.commit()


def main() -> None:
    connection = sqlite3.connect(get_settings().database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    seed(connection)
    print("Seeded development-only admin, recruiter, and student accounts.")
    connection.close()


if __name__ == "__main__":
    main()