from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationResult:
    raw_skill: str
    canonical_skill_id: int | None
    canonical_skill: str | None
    matched_by: str
    confidence: float
    status: str


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def ensure_tables(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS skill_normalization_cache (
            raw_skill TEXT PRIMARY KEY,
            canonical_skill_id INTEGER REFERENCES skills(skill_id),
            status TEXT NOT NULL CHECK (status IN ('normalized', 'unresolved', 'review_required')),
            confidence REAL NOT NULL,
            matching_method TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS skill_gap_analysis (
            skill_id INTEGER PRIMARY KEY REFERENCES skills(skill_id),
            analyzed_job_count INTEGER NOT NULL,
            demand_score REAL NOT NULL,
            curriculum_course_count INTEGER NOT NULL,
            curriculum_coverage REAL NOT NULL,
            gap_score REAL NOT NULL,
            gap_status TEXT NOT NULL CHECK (gap_status IN ('covered', 'gap', 'no_demand')),
            calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_skill_cache_status ON skill_normalization_cache(status);
        CREATE INDEX IF NOT EXISTS idx_skill_gap_score ON skill_gap_analysis(gap_score DESC);
    """)


def normalize_skill(connection: sqlite3.Connection, raw_skill: str) -> NormalizationResult:
    raw_skill = raw_skill.strip()
    cached = connection.execute(
        """SELECT c.raw_skill, c.canonical_skill_id, s.canonical_name, c.matching_method, c.confidence, c.status
           FROM skill_normalization_cache c LEFT JOIN skills s ON s.skill_id = c.canonical_skill_id
           WHERE c.raw_skill = ?""", (raw_skill,)
    ).fetchone()
    if cached:
        return NormalizationResult(raw_skill, cached["canonical_skill_id"], cached["canonical_name"], cached["matching_method"], cached["confidence"], cached["status"])

    canonical = connection.execute("SELECT skill_id AS canonical_skill_id, canonical_name FROM skills WHERE lower(canonical_name) = lower(?)", (raw_skill,)).fetchone()
    method = "canonical_exact"
    confidence = 1.0
    if not canonical:
        canonical = connection.execute(
            "SELECT skill_id AS canonical_skill_id, canonical_name FROM skills WHERE lower(replace(replace(replace(canonical_name, ' ', ''), '.', ''), '-', '')) = lower(?)",
            (_key(raw_skill),),
        ).fetchone()
        method = "canonical_normalized" if canonical else "unresolved"
    if not canonical:
        canonical = connection.execute(
            """SELECT a.raw_skill, a.canonical_skill_id, s.canonical_name, a.confidence
               FROM skill_aliases a JOIN skills s ON s.skill_id = a.canonical_skill_id
               WHERE lower(a.raw_skill) = lower(?)""", (raw_skill,)
        ).fetchone()
        if canonical:
            method, confidence = "alias", float(canonical["confidence"])
    if not canonical:
        aliases = connection.execute(
            """SELECT a.raw_skill, a.canonical_skill_id, s.canonical_name, a.confidence
               FROM skill_aliases a JOIN skills s ON s.skill_id = a.canonical_skill_id"""
        ).fetchall()
        canonical = next((row for row in aliases if _key(row["raw_skill"]) == _key(raw_skill)), None)
        if canonical:
            method, confidence = "alias_normalized", float(canonical["confidence"])

    result = NormalizationResult(
        raw_skill, canonical["canonical_skill_id"] if canonical else None,
        canonical["canonical_name"] if canonical else None,
        method if canonical else "unresolved", confidence if canonical else 0.0,
        "normalized" if canonical else "unresolved",
    )
    connection.execute(
        """INSERT INTO skill_normalization_cache(raw_skill, canonical_skill_id, status, confidence, matching_method)
           VALUES (?, ?, ?, ?, ?) ON CONFLICT(raw_skill) DO UPDATE SET canonical_skill_id=excluded.canonical_skill_id,
           status=excluded.status, confidence=excluded.confidence, matching_method=excluded.matching_method,
           updated_at=CURRENT_TIMESTAMP""",
        (result.raw_skill, result.canonical_skill_id, result.status, result.confidence, result.matched_by),
    )
    return result


def normalize_all_observations(connection: sqlite3.Connection) -> dict[str, int]:
    ensure_tables(connection)
    raw_values = set()
    for table, column in [("job_skill_observations", "raw_skill"), ("curriculum_skill_observations", "observed_skill"), ("assessment_questions", "observed_skill"), ("learning_resources", "observed_skill")]:
        raw_values.update(row[0] for row in connection.execute(f"SELECT DISTINCT {column} FROM {table}"))
    normalized = unresolved = 0
    for raw in sorted(raw_values):
        result = normalize_skill(connection, raw)
        normalized += result.status == "normalized"
        unresolved += result.status == "unresolved"
    for table, column in [("job_skill_observations", "raw_skill"), ("curriculum_skill_observations", "observed_skill"), ("assessment_questions", "observed_skill"), ("learning_resources", "observed_skill")]:
        connection.execute(f"""UPDATE {table} SET canonical_skill_id = (SELECT canonical_skill_id FROM skill_normalization_cache WHERE raw_skill = {table}.{column}) WHERE {column} IN (SELECT raw_skill FROM skill_normalization_cache WHERE status = 'normalized')""")
    connection.commit()
    return {"observations": len(raw_values), "normalized": normalized, "unresolved": unresolved}
