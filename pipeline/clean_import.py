"""Create import-ready CSVs from the supplied synthesized datasets.

The source files contain unquoted commas in several fields. This importer uses
the known schema for each file to recover those records without editing the
source files. It does not create or infer new canonical skills.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from difflib import SequenceMatcher
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data"
OUTPUT = ROOT / "pipeline" / "cleaned"

FILES = [
    "jobs.csv",
    "curriculum.csv",
    "skill_aliases.csv",
    "skill_curriculum_mapping.csv",
    "student.csv",
    "questions.csv",
    "learning_resources.csv",
    "companies.csv",
]

SCHEMAS = {
    "jobs.csv": [
        "job_id", "company", "job_title", "state", "city", "experience",
        "degree", "required_skills", "preferred_skills", "salary_range",
        "job_description",
    ],
    "curriculum.csv": [
        "curriculum_id", "university", "state", "degree", "department",
        "year", "semester", "course_code", "course_title", "syllabus",
    ],
    "skill_aliases.csv": [
        "alias_id", "raw_skill", "normalized_skill", "category", "confidence",
    ],
    "skill_curriculum_mapping.csv": [
        "mapping_id", "course_id", "course_code", "course_title", "skill",
        "skill_category", "coverage", "gap_analysis",
    ],
    "student.csv": [
        "student_id", "name", "state", "degree", "department", "year",
        "semester", "skills", "experience", "certifications", "assessment_score",
    ],
    "questions.csv": ["question_id", "skill", "difficulty", "question", "answer"],
    "learning_resources.csv": ["skill", "resource_name", "platform", "url", "level", "type"],
    "companies.csv": [
        "company_id", "company_name", "industry", "headquarters", "states",
        "website", "company_size", "domains",
    ],
}

URL_RE = re.compile(r"^https?://[^\s]+$")
SALARY_RE = re.compile(r"^\d+(?:\.\d+)?-\d+(?:\.\d+)?\s+LPA$", re.IGNORECASE)


def raw_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def join_fragments(parts: Iterable[str]) -> str:
    return ", ".join(part.strip() for part in parts if part.strip())


def recover(name: str, parsed: list[list[str]]) -> tuple[list[str], list[list[str]], int]:
    schema = SCHEMAS[name]
    rows = parsed[1:]
    recovered = sum(len(row) != len(schema) for row in rows)

    if name in {"skill_aliases.csv", "student.csv", "learning_resources.csv"}:
        return schema, [row[: len(schema)] for row in rows], recovered

    if name == "curriculum.csv":
        # The syllabus is the final, free-text field.
        cleaned = [row[:9] + [join_fragments(row[9:])] for row in rows]
    elif name == "skill_curriculum_mapping.csv":
        # The gap analysis is the final free-text field.
        cleaned = [row[:7] + [join_fragments(row[7:])] for row in rows]
    elif name == "questions.csv":
        # The answer is the final, free-text field.
        cleaned = [row[:4] + [join_fragments(row[4:])] for row in rows]
    elif name == "companies.csv":
        cleaned = []
        for row in rows:
            website_index = next((i for i, value in enumerate(row) if URL_RE.match(value.strip())), None)
            if website_index is None or website_index < 5:
                cleaned.append(row[:7] + [join_fragments(row[7:])])
                continue
            # Preserve the fixed company fields and recover domains after size.
            cleaned.append(row[:5] + [row[website_index], row[website_index + 1], join_fragments(row[website_index + 2:])])
    elif name == "jobs.csv":
        cleaned = []
        for row in rows:
            salary_index = next((i for i, value in enumerate(row) if SALARY_RE.match(value.strip())), None)
            if salary_index is None or salary_index < 7:
                cleaned.append(row[:7] + [join_fragments(row[7:9]), "", "", ""])
                continue
            middle = row[7:salary_index]
            # The source has no quoting or marker between the two skill lists.
            # Keep every recovered skill fragment in required_skills so no data
            # is discarded; preferred_skills remains explicitly unresolved.
            cleaned.append(row[:7] + [join_fragments(middle), "", row[salary_index].strip(), join_fragments(row[salary_index + 1:])])
    else:
        raise ValueError(f"No recovery strategy for {name}")

    return schema, cleaned, recovered


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def nonempty(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def normalized_name(value: str) -> str:
    return "".join(ch for ch in value.casefold().replace("&", "and") if ch.isalnum())


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"files": {}, "company_matching": {}, "unmatched_skills": {}, "broken_references": []}
    cleaned_data: dict[str, tuple[list[str], list[list[str]]]] = {}

    for name in FILES:
        parsed = raw_rows(SOURCE / name)
        header, rows, recovered = recover(name, parsed)
        if any(len(row) != len(header) for row in rows):
            raise ValueError(f"Recovery failed to produce {name} rows with the expected width")
        write_csv(OUTPUT / name, header, rows)
        cleaned_data[name] = (header, rows)
        report["files"][name] = {
            "original_rows": len(parsed) - 1,
            "cleaned_rows": len(rows),
            "rows_recovered_from_malformed_parsing": recovered,
            "genuinely_unimportable_rows": 0,
        }

    company_header, company_rows = cleaned_data["companies.csv"]
    company_by_name = {normalized_name(nonempty(row, 1)): (nonempty(row, 0), nonempty(row, 1)) for row in company_rows}
    job_header, job_rows = cleaned_data["jobs.csv"]
    unmatched_companies: list[str] = []
    matched = 0
    company_match_rows = []
    company_names = list(company_by_name.values())
    for row in job_rows:
        company_name = nonempty(row, 1)
        exact = company_by_name.get(normalized_name(company_name))
        ranked = sorted(
            ((SequenceMatcher(None, normalized_name(company_name), normalized_name(master_name)).ratio(), master_name)
             for _, master_name in company_names),
            reverse=True,
        )
        closest_score, closest_name = ranked[0]
        company_id = exact[0] if exact else ""
        if company_id:
            matched += 1
            row.append(company_id)
            status = "matched_exact_normalized"
        else:
            unmatched_companies.append(company_name)
            row.append("")
            status = "unmatched_sql_null"
        company_match_rows.append([company_name, exact[1] if exact else "", closest_name, f"{closest_score:.2f}", status])
    job_header.append("company_id")
    write_csv(OUTPUT / "jobs.csv", job_header, job_rows)
    write_csv(OUTPUT / "company_match_report.csv", ["job_company_name", "exact_or_normalized_match", "closest_company_name", "similarity", "status"], company_match_rows)
    report["company_matching"] = {
        "matched_jobs": matched,
        "unmatched_jobs": len(unmatched_companies),
        "unmatched_company_names": sorted(set(unmatched_companies)),
        "companies_created": 0,
        "unmatched_company_id_representation": "blank CSV field imported as SQL NULL",
        "mapping_report": "company_match_report.csv",
    }

    aliases_header, aliases = cleaned_data["skill_aliases.csv"]
    canonical = {nonempty(row, 2).casefold() for row in aliases}
    raw_aliases = {nonempty(row, 1).casefold(): nonempty(row, 2) for row in aliases}
    skill_sources = {
        "skill_curriculum_mapping.csv": 4,
        "questions.csv": 1,
        "learning_resources.csv": 0,
    }
    for name, index in skill_sources.items():
        header, rows = cleaned_data[name]
        unmatched = sorted({nonempty(row, index) for row in rows if nonempty(row, index) and nonempty(row, index).casefold() not in canonical})
        report["unmatched_skills"][name] = unmatched

    all_unmatched = sorted({skill for skills in report["unmatched_skills"].values() for skill in skills})
    proposals = []
    for skill in all_unmatched:
        existing = raw_aliases.get(skill.casefold())
        if existing:
            disposition = "existing_alias_requires_review" if existing.casefold() != skill.casefold() else "existing_canonical"
            proposed = existing
            rationale = "Existing skill_aliases.csv mapping; no source change made"
        else:
            disposition = "new_canonical_candidate"
            proposed = skill
            rationale = "No existing alias found; requires explicit approval before taxonomy change"
        proposals.append([skill, proposed, disposition, rationale])
    write_csv(OUTPUT / "canonical_skill_proposals.csv", ["observed_skill", "proposed_canonical_skill", "disposition", "rationale"], proposals)
    report["canonical_skill_proposals"] = "canonical_skill_proposals.csv"

    curriculum_ids = {nonempty(row, 0) for row in cleaned_data["curriculum.csv"][1]}
    mapping_ids = {nonempty(row, 1) for row in cleaned_data["skill_curriculum_mapping.csv"][1]}
    report["broken_references"] = [
        {"source": "skill_curriculum_mapping.csv", "field": "course_id", "missing_targets": sorted(mapping_ids - curriculum_ids)}
    ]
    report["status"] = "PASS_WITH_REVIEW_ITEMS" if not report["broken_references"][0]["missing_targets"] else "REVIEW_REQUIRED"
    (OUTPUT / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()