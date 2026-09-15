from __future__ import annotations

import re
import sqlite3

from .normalization import normalize_skill
from .student import role_skills


def _skill_candidates(connection: sqlite3.Connection, text: str) -> list[str]:
    terms = [row[0] for row in connection.execute("SELECT canonical_name FROM skills")] + [row[0] for row in connection.execute("SELECT raw_skill FROM skill_aliases")]
    found = [term for term in terms if re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.IGNORECASE)]
    sections = re.findall(r"(?:skills?|technologies|tools|software|subjects?)\s*[:\-]\s*([^\.\n]+)", text, re.IGNORECASE)
    for section in sections:
        found.extend(part.strip() for part in re.split(r",|;|\||/|\s+and\s+", section, flags=re.IGNORECASE) if 1 < len(part.strip()) < 60)
    unique: list[str] = []
    for term in found:
        if term and term.casefold() not in {item.casefold() for item in unique}:
            unique.append(term)
    return unique


def analyze(connection: sqlite3.Connection, mode: str, text: str, target_role: str | None = None) -> dict[str, object]:
    normalized = []
    unresolved = []
    for raw in _skill_candidates(connection, text):
        result = normalize_skill(connection, raw)
        item = {"raw_skill": raw, "canonical_skill_id": result.canonical_skill_id, "canonical_skill": result.canonical_skill, "matched_by": result.matched_by, "confidence": result.confidence, "status": result.status}
        (normalized if result.canonical_skill_id is not None else unresolved).append(item)
    connection.commit()
    canonical_ids = {item["canonical_skill_id"] for item in normalized}
    implications = []
    for item in normalized:
        skill_id = item["canonical_skill_id"]
        row = connection.execute("SELECT analyzed_job_count, demand_score, curriculum_course_count, curriculum_coverage, gap_score, gap_status FROM skill_gap_analysis WHERE skill_id = ?", (skill_id,)).fetchone()
        if row:
            implications.append({"skill_id": skill_id, "skill": item["canonical_skill"], **dict(row)})
    comparison = None
    if target_role:
        required = role_skills(connection, target_role)
        required_ids = {row["skill_id"] for row in required}
        comparison = {"target_role": target_role, "matched_skills": sorted(canonical_ids & required_ids), "missing_skills": [dict(row) for row in required if row["skill_id"] not in canonical_ids]}
    return {"mode": mode, "skills": normalized, "unresolved_skills": unresolved, "implications": implications, "target_role_comparison": comparison, "stored_text": False}