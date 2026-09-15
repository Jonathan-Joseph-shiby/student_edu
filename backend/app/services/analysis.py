from __future__ import annotations

import sqlite3

from .normalization import ensure_tables, normalize_all_observations


def recompute_analysis(connection: sqlite3.Connection) -> dict[str, int]:
    ensure_tables(connection)
    normalization = normalize_all_observations(connection)
    total_jobs = connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    connection.execute("DELETE FROM skill_gap_analysis")
    skills = connection.execute("SELECT skill_id FROM skills ORDER BY skill_id").fetchall()
    for skill in skills:
        skill_id = skill[0]
        job_count = connection.execute("SELECT COUNT(DISTINCT job_id) FROM job_skill_observations WHERE canonical_skill_id = ?", (skill_id,)).fetchone()[0]
        course_count = connection.execute("SELECT COUNT(DISTINCT course_id) FROM curriculum_skill_observations WHERE canonical_skill_id = ?", (skill_id,)).fetchone()[0]
        demand_score = job_count / total_jobs if total_jobs else 0.0
        coverage = 1.0 if course_count > 0 else 0.0
        gap_score = demand_score * (1.0 - coverage)
        status = "gap" if gap_score > 0 else ("covered" if job_count > 0 else "no_demand")
        connection.execute(
            """INSERT INTO skill_gap_analysis(skill_id, analyzed_job_count, demand_score, curriculum_course_count,
                     curriculum_coverage, gap_score, gap_status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (skill_id, job_count, demand_score, course_count, coverage, gap_score, status),
        )
    connection.commit()
    return {**normalization, "total_jobs": total_jobs, "total_canonical_skills": len(skills)}


def skill_rows(connection: sqlite3.Connection, gaps_only: bool = False) -> list[sqlite3.Row]:
    ensure_tables(connection)
    where = "WHERE a.gap_status = 'gap'" if gaps_only else ""
    return connection.execute(
        f"""SELECT s.skill_id, s.canonical_name, a.analyzed_job_count, a.demand_score,
                   a.curriculum_course_count, a.curriculum_coverage, a.gap_score,
                   a.gap_status, a.calculated_at FROM skill_gap_analysis a
            JOIN skills s ON s.skill_id = a.skill_id {where}
            ORDER BY a.gap_score DESC, a.demand_score DESC, s.canonical_name"""
    ).fetchall()


def skill_detail(connection: sqlite3.Connection, skill_id: int) -> sqlite3.Row | None:
    ensure_tables(connection)
    return connection.execute(
        """SELECT s.skill_id, s.canonical_name, a.analyzed_job_count, a.demand_score,
                  a.curriculum_course_count, a.curriculum_coverage, a.gap_score,
                  a.gap_status, a.calculated_at FROM skill_gap_analysis a
           JOIN skills s ON s.skill_id = a.skill_id WHERE s.skill_id = ?""",
        (skill_id,),
    ).fetchone()


def source_jobs(connection: sqlite3.Connection, skill_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT j.job_id, j.job_title, j.source_company_name, j.company_id,
                  j.state, j.city, j.job_description, o.raw_skill,
                  NULL AS source_url, NULL AS posting_date
           FROM job_postings j JOIN job_skill_observations o ON o.job_id = j.job_id
           WHERE o.canonical_skill_id = ? ORDER BY j.job_id""",
        (skill_id,),
    ).fetchall()


def unresolved_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure_tables(connection)
    return connection.execute(
        """SELECT c.raw_skill, c.status, c.confidence, c.matching_method,
                  (SELECT COUNT(*) FROM job_skill_observations j WHERE j.raw_skill = c.raw_skill)
                  + (SELECT COUNT(*) FROM curriculum_skill_observations m WHERE m.observed_skill = c.raw_skill)
                  + (SELECT COUNT(*) FROM assessment_questions q WHERE q.observed_skill = c.raw_skill)
                  + (SELECT COUNT(*) FROM learning_resources r WHERE r.observed_skill = c.raw_skill) AS observation_count
           FROM skill_normalization_cache c WHERE c.status <> 'normalized'
           ORDER BY observation_count DESC, c.raw_skill"""
    ).fetchall()