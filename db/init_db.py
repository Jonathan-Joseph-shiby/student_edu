"""Initialize SkillBridge SQLite from pipeline/cleaned CSVs."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "pipeline" / "cleaned"
DB_PATH = ROOT / "db" / "industrypulse.sqlite3"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def read_csv(name: str) -> list[dict[str, str]]:
    with (CLEANED / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_skills(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    companies = read_csv("companies.csv")
    aliases = read_csv("skill_aliases.csv")
    jobs = read_csv("jobs.csv")
    curricula = read_csv("curriculum.csv")
    mappings = read_csv("skill_curriculum_mapping.csv")
    students = read_csv("student.csv")
    questions = read_csv("questions.csv")
    resources = read_csv("learning_resources.csv")

    connection.executemany(
        "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(r["company_id"], r["company_name"], r["industry"], r["headquarters"], r["states"], r["website"], r["company_size"], r["domains"]) for r in companies],
    )

    canonical_by_name: dict[str, int] = {}
    for row in aliases:
        key = row["normalized_skill"].casefold()
        if key not in canonical_by_name:
            cursor = connection.execute("INSERT INTO skills(canonical_name, category) VALUES (?, ?)", (row["normalized_skill"], row["category"]))
            canonical_by_name[key] = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO skill_aliases VALUES (?, ?, ?, ?, ?)",
            (row["alias_id"], row["raw_skill"], canonical_by_name[key], row["category"], float(row["confidence"])),
        )

    raw_to_skill = {row["raw_skill"].casefold(): canonical_by_name[row["normalized_skill"].casefold()] for row in aliases}

    connection.executemany(
        "INSERT INTO curricula VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(r["curriculum_id"], r["university"], r["state"], r["degree"], r["department"], int(r["year"]), int(r["semester"]), r["course_code"], r["course_title"], r["syllabus"]) for r in curricula],
    )
    connection.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(r["student_id"], r["name"], r["state"], r["degree"], r["department"], int(r["year"]), int(r["semester"]), r["skills"], r["experience"], r["certifications"], float(r["assessment_score"])) for r in students],
    )

    company_by_name = {r["company_name"].casefold(): r["company_id"] for r in companies}
    for row in jobs:
        company_id = company_by_name.get(row["company"].casefold()) or None
        connection.execute(
            "INSERT INTO job_postings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row["job_id"], company_id, row["company"], row["job_title"], row["state"], row["city"], row["experience"], row["degree"], row["salary_range"], row["job_description"]),
        )
        for raw_skill in split_skills(row["required_skills"]):
            connection.execute(
                "INSERT INTO job_skill_observations(job_id, raw_skill, canonical_skill_id, skill_requirement) VALUES (?, ?, ?, 'required')",
                (row["job_id"], raw_skill, raw_to_skill.get(raw_skill.casefold())),
            )

    for row in mappings:
        connection.execute(
            "INSERT INTO curriculum_skill_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row["mapping_id"], row["course_id"], row["course_code"], row["course_title"], row["skill"], canonical_by_name.get(row["skill"].casefold()), row["skill_category"], row["coverage"], row["gap_analysis"]),
        )
    for row in questions:
        connection.execute(
            "INSERT INTO assessment_questions VALUES (?, ?, ?, ?, ?, ?)",
            (row["question_id"], row["skill"], raw_to_skill.get(row["skill"].casefold()) or canonical_by_name.get(row["skill"].casefold()), row["difficulty"], row["question"], row["answer"]),
        )
    for row in resources:
        connection.execute(
            "INSERT INTO learning_resources(observed_skill, canonical_skill_id, resource_name, platform, url, level, type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["skill"], raw_to_skill.get(row["skill"].casefold()) or canonical_by_name.get(row["skill"].casefold()), row["resource_name"], row["platform"], row["url"], row["level"], row["type"]),
        )

    unresolved: dict[str, set[str]] = {}
    for table, column, source in [
        ("job_skill_observations", "raw_skill", "jobs"),
        ("curriculum_skill_observations", "observed_skill", "curriculum"),
        ("assessment_questions", "observed_skill", "questions"),
        ("learning_resources", "observed_skill", "learning_resources"),
    ]:
        rows = connection.execute(f"SELECT {column} FROM {table} WHERE canonical_skill_id IS NULL").fetchall()
        for (skill,) in rows:
            unresolved.setdefault(skill, set()).add(source)
    connection.executemany(
        "INSERT INTO unresolved_skill_observations VALUES (?, ?)",
        [(skill, ", ".join(sorted(sources))) for skill, sources in sorted(unresolved.items())],
    )
    connection.commit()

    checks = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ["companies", "skills", "skill_aliases", "job_postings", "job_skill_observations", "curricula", "curriculum_skill_observations", "students", "assessment_questions", "learning_resources", "unresolved_skill_observations"]
    }
    checks["jobs_with_null_company_id"] = connection.execute("SELECT COUNT(*) FROM job_postings WHERE company_id IS NULL").fetchone()[0]
    checks["broken_curriculum_references"] = connection.execute("SELECT COUNT(*) FROM curriculum_skill_observations WHERE course_id NOT IN (SELECT curriculum_id FROM curricula)").fetchone()[0]
    connection.close()
    (ROOT / "db" / "initialization_report.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()