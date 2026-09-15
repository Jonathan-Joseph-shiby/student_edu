from __future__ import annotations

import sqlite3
from collections import defaultdict

from .normalization import ensure_tables, normalize_skill


def next_student_id(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT student_id FROM students WHERE student_id LIKE 'S%'").fetchall()
    highest = 0
    for row in rows:
        value = row[0]
        suffix = value[1:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"S{highest + 1:03d}"


def create_student_profile(connection: sqlite3.Connection, email: str, profile: dict[str, object] | None = None) -> str:
    profile = profile or {}
    student_id = next_student_id(connection)
    name = str(profile.get("name") or email.split("@", 1)[0])
    connection.execute(
        """INSERT INTO students(
               student_id, name, state, degree, department, year, semester,
               skills, experience, certifications, assessment_score
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, name, str(profile.get("state") or "Not specified"), str(profile.get("degree") or "Not specified"), str(profile.get("department") or "Not specified"), int(profile.get("year") or 1), 1, str(profile.get("skills") or ""), "", "", 0),
    )
    return student_id


def ensure_student_tables(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS student_target_roles (
            student_id TEXT PRIMARY KEY REFERENCES students(student_id), target_role TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS assessment_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL REFERENCES students(student_id),
            version INTEGER NOT NULL, total_score REAL NOT NULL, submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, version)
        );
        CREATE TABLE IF NOT EXISTS assessment_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL REFERENCES assessment_attempts(attempt_id),
            question_id TEXT NOT NULL REFERENCES assessment_questions(question_id), selected_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)), UNIQUE(attempt_id, question_id)
        );
        CREATE TABLE IF NOT EXISTS student_skill_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL REFERENCES students(student_id),
            attempt_id INTEGER NOT NULL REFERENCES assessment_attempts(attempt_id), skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
            score REAL NOT NULL CHECK (score >= 0 AND score <= 100), level TEXT NOT NULL,
            UNIQUE(attempt_id, skill_id)
        );
        CREATE TABLE IF NOT EXISTS student_progress (
            progress_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL REFERENCES students(student_id),
            skill_id INTEGER NOT NULL REFERENCES skills(skill_id), resource_id INTEGER REFERENCES learning_resources(resource_id),
            status TEXT NOT NULL, week_number INTEGER NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, skill_id, resource_id)
        );
    """)


def student_id_for_user(user: sqlite3.Row) -> str:
    if user["role"] != "student" or not user["student_id"]:
        raise PermissionError("A linked student account is required")
    return user["student_id"]


def level_for_score(score: float) -> str:
    if score < 40:
        return "Beginner"
    if score < 70:
        return "Intermediate"
    if score < 85:
        return "Good"
    return "Strong"


def roles(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute("SELECT job_title AS target_role, COUNT(*) AS job_count FROM job_postings GROUP BY job_title ORDER BY job_title").fetchall()


def role_skills(connection: sqlite3.Connection, target_role: str) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT s.skill_id, s.canonical_name, COUNT(DISTINCT j.job_id) AS jobs_requiring_skill,
                  COUNT(DISTINCT j.job_id) * 1.0 / (SELECT COUNT(*) FROM job_postings WHERE job_title = ?) AS demand_score
           FROM job_postings j JOIN job_skill_observations o ON o.job_id = j.job_id
           JOIN skills s ON s.skill_id = o.canonical_skill_id WHERE j.job_title = ?
           GROUP BY s.skill_id, s.canonical_name ORDER BY demand_score DESC, s.canonical_name""",
        (target_role, target_role),
    ).fetchall()


def current_scores(connection: sqlite3.Connection, student_id: str) -> dict[int, float]:
    rows = connection.execute(
        """SELECT x.skill_id, x.score FROM student_skill_scores x JOIN assessment_attempts a ON a.attempt_id = x.attempt_id
           WHERE x.student_id = ? AND a.version = (SELECT MAX(version) FROM assessment_attempts WHERE student_id = ?)""",
        (student_id, student_id),
    ).fetchall()
    scores = {row["skill_id"]: row["score"] for row in rows}
    student = connection.execute("SELECT skills FROM students WHERE student_id = ?", (student_id,)).fetchone()
    for raw in [part.strip() for part in (student[0] if student else "").split(",") if part.strip()]:
        result = normalize_skill(connection, raw)
        if result.canonical_skill_id is not None:
            scores.setdefault(result.canonical_skill_id, 100.0)
    return scores


def personal_gap(connection: sqlite3.Connection, student_id: str) -> dict[str, object]:
    ensure_tables(connection)
    target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
    if not target:
        return {"target_role": None, "items": [], "readiness_score": None}
    scores = current_scores(connection, student_id)
    items = []
    for row in role_skills(connection, target[0]):
        score = float(scores.get(row["skill_id"], 0.0))
        gap = 100.0 - score
        priority = row["demand_score"] * (gap / 100.0)
        priority_label = "High" if priority >= 0.15 else ("Medium" if priority >= 0.05 else "Low")
        items.append({"skill_id": row["skill_id"], "skill": row["canonical_name"], "industry_requirement": row["demand_score"], "student_score": score, "level": level_for_score(score), "gap_score": gap, "priority_score": priority, "priority": priority_label, "recommended_action": "Learn and reassess" if gap > 0 else "Maintain and reassess"})
    return {"target_role": target[0], "items": sorted(items, key=lambda item: (-item["priority_score"], item["skill"])), "readiness_score": readiness(connection, student_id, target[0])}


def readiness(connection: sqlite3.Connection, student_id: str, target_role: str | None = None) -> float | None:
    if target_role is None:
        target = connection.execute("SELECT target_role FROM student_target_roles WHERE student_id = ?", (student_id,)).fetchone()
        target_role = target[0] if target else None
    if not target_role:
        return None
    scores = current_scores(connection, student_id)
    requirements = role_skills(connection, target_role)
    if not requirements:
        return None
    denominator = sum(row["demand_score"] for row in requirements)
    return round(sum(row["demand_score"] * scores.get(row["skill_id"], 0.0) for row in requirements) / denominator, 2) if denominator else 0.0


def recommendations(connection: sqlite3.Connection, student_id: str) -> list[dict[str, object]]:
    result = personal_gap(connection, student_id)
    items = []
    for gap in result["items"]:
        resources = connection.execute("SELECT resource_id, resource_name, platform, url, level, type FROM learning_resources WHERE canonical_skill_id = ? OR lower(observed_skill) = lower(?)", (gap["skill_id"], gap["skill"])).fetchall()
        if resources:
            for resource in resources:
                item = dict(resource)
                item.update({"skill_id": gap["skill_id"], "skill": gap["skill"], "reason": "Matches a target-role skill gap"})
                items.append(item)
        else:
            items.append({"skill_id": gap["skill_id"], "skill": gap["skill"], "resource_id": None, "resource_name": None, "platform": None, "url": None, "level": None, "type": None, "reason": "Learning resource not available in current dataset"})
    return items


def roadmap(connection: sqlite3.Connection, student_id: str) -> list[dict[str, object]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for week, item in enumerate(recommendations(connection, student_id), 1):
        item["week_number"] = week
        item["practice"] = "Practice the skill using the recommended resource, then reassess."
        grouped[week].append(item)
    return [{"week_number": week, "items": items} for week, items in grouped.items()]


def submit_assessment(connection: sqlite3.Connection, student_id: str, answers: list[dict[str, str]]) -> dict[str, object]:
    ensure_tables(connection)
    questions = {}
    for answer in answers:
        if answer["question_id"] in questions:
            raise ValueError("Duplicate question_id in assessment")
        question = connection.execute("SELECT * FROM assessment_questions WHERE question_id = ?", (answer["question_id"],)).fetchone()
        if question is None:
            raise ValueError("Unknown question_id")
        questions[answer["question_id"]] = (answer, question)
    version = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM assessment_attempts WHERE student_id = ?", (student_id,)).fetchone()[0]
    total = sum(answer["answer"].strip().casefold() == question["answer"].strip().casefold() for answer, question in questions.values())
    total_score = round(total * 100.0 / len(questions), 2)
    cursor = connection.execute("INSERT INTO assessment_attempts(student_id, version, total_score) VALUES (?, ?, ?)", (student_id, version, total_score))
    attempt_id = cursor.lastrowid
    by_skill: dict[int, list[bool]] = defaultdict(list)
    for answer, question in questions.values():
        correct = answer["answer"].strip().casefold() == question["answer"].strip().casefold()
        connection.execute("INSERT INTO assessment_answers(attempt_id, question_id, selected_answer, is_correct) VALUES (?, ?, ?, ?)", (attempt_id, question["question_id"], answer["answer"], int(correct)))
        if question["canonical_skill_id"] is not None:
            by_skill[question["canonical_skill_id"]].append(correct)
    for skill_id, results in by_skill.items():
        score = round(sum(results) * 100.0 / len(results), 2)
        connection.execute("INSERT INTO student_skill_scores(student_id, attempt_id, skill_id, score, level) VALUES (?, ?, ?, ?, ?)", (student_id, attempt_id, skill_id, score, level_for_score(score)))
    connection.commit()
    return {"attempt_id": attempt_id, "version": version, "total_score": total_score, "skill_scores": [{"skill_id": skill_id, "score": round(sum(values) * 100.0 / len(values), 2), "level": level_for_score(round(sum(values) * 100.0 / len(values), 2))} for skill_id, values in by_skill.items()]}