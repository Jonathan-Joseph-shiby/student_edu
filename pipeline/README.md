# Safe Import Pipeline

Run from the repository root:

```powershell
python pipeline\clean_import.py
```

The script reads only from `data/` and writes import-ready files to
`pipeline/cleaned/`. It never edits, renames, deletes, or replaces the original
datasets.

## Import decisions

- Unquoted commas are recovered using each dataset's known schema. Free-text
  and list fragments are joined with commas, so valid records are retained.
- `course_id`/`course_code` repetition in the mapping file is preserved as
  many-to-many data. Repeated `CS201` values in the curriculum remain separate
  records because `curriculum_id` is the primary key.
- Jobs are matched to companies only by exact or normalized company name. An
  unmatched job keeps its original company name and receives a blank
  `company_id`; the database importer must convert that blank to SQL `NULL`.
  No company is invented or renamed. See `company_match_report.csv`.
- The malformed jobs source does not delimit `required_skills` from
  `preferred_skills`. All recovered skill fragments are therefore preserved as
  required skills for the prototype. `preferred_skills` is left blank; no
  preferred skill is fabricated or guessed.
- Existing raw-skill aliases are available for normalization, including
  `Excel -> Microsoft Excel` and `ReactJS -> React`.
- Unmatched labels are written to `canonical_skill_proposals.csv`. Existing
  mappings that may be too broad, such as `PostgreSQL -> SQL` or
  `MongoDB -> NoSQL Database`, are marked for review. New canonical candidates
  are reported but are never added to `skill_aliases.csv` automatically.