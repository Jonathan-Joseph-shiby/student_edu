# SkillBridge

SkillBridge is an India-focused EduTech prototype connecting industry demand,
curriculum coverage, student skills, and job readiness.

## Backend setup

Use Python 3.14 or a compatible supported Python environment:

```powershell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a private `JWT_SECRET_KEY`. The example
values are development placeholders only. The backend currently reads standard
environment variables; PowerShell users can load them for a session with
`$env:JWT_SECRET_KEY = "..."`.

## Initialize the database

The initializer reads only `pipeline/cleaned/` and recreates the SQLite file.
It does not modify the original CSV files in `data/`.

```powershell
python db\init_db.py
```

Seed development-only demo accounts after initialization:

```powershell
python backend\seed_demo.py
```

Demo credentials are controlled by the `DEMO_*` environment variables. The
defaults in `.env.example` are placeholders and must not be used in production.
The student demo account links to existing student `S001`; no student data is
created by seeding.

## New student registration

`POST /api/v1/auth/register` with `role: "student"` and no `student_id`
creates a default student profile and links it to the new user in one SQLite
transaction. The next ID is generated from the highest existing numeric
`S...` ID under an immediate write lock, so concurrent registrations cannot
reuse an ID. The generated profile starts with editable placeholder values;
the student can update their name, experience, and certifications through
`PUT /api/v1/student/profile`, then enter the target-role and assessment
workflow.

The current frontend has login but no student signup screen. Backend
registration is covered by `tests/test_new_student_registration.py`, which
uses an isolated copy of the database and never adds a development account to
the seeded demo database.

## Start FastAPI

```powershell
$env:JWT_SECRET_KEY = "your-local-development-secret"
uvicorn backend.app.main:app --reload
```

The API is served at `http://127.0.0.1:8000`.

## Authentication API

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/admin/test`
- `GET /api/v1/recruiter/test`
- `GET /api/v1/student/test`

Roles are `student`, `recruiter`, and `admin`. Passwords are stored as Argon2
hashes, and access tokens are signed JWTs with expiration. Password hashes are
never returned by the API.

## Phase 3 intelligence

Normalization is deterministic and cached in `skill_normalization_cache`. It
checks exact canonical names, exact aliases, and punctuation/spacing-normalized
aliases. It never uses fuzzy matching to merge distinct technologies. Unknown
skills remain unresolved with a nullable canonical ID and are exposed through
the admin unresolved-skills endpoint.

Industry demand counts distinct job postings per canonical skill, so repeated
mentions in one job do not inflate demand. Demand is `jobs_requiring_skill /
total_analyzed_jobs`. Curriculum coverage is `1` when at least one curriculum
course mapping uses the canonical skill, otherwise `0`. The gap formula is:

`gap_score = demand_score * (1 - curriculum_coverage)`

Computed results are persisted in `skill_gap_analysis`; GET requests do not
recalculate the dataset. An admin must call
`POST /api/v1/admin/analysis/recompute`. Traceability joins each canonical
skill back to the original job company name, title, location, description, and
raw skill observation. Source URL and posting date remain null because those
fields are not present in the supplied dataset.

Phase 3 endpoints include `GET /api/v1/skills`,
`GET /api/v1/industry/demand`, `GET /api/v1/curriculum/coverage`,
`GET /api/v1/curriculum/gaps`, authenticated
`GET /api/v1/analysis/skill-gaps`, authenticated source drilldowns, admin
recomputation, and admin unresolved-skill reporting. Optional Anthropic
configuration is read from `ANTHROPIC_API_KEY`, but no AI call is made by the
core pipeline or dashboard reads. Future AI results must validate against the
existing canonical taxonomy before caching.

## Tests

Run the Phase 2 suite:

```powershell
pytest -q
```

Tests use temporary SQLite databases and do not mutate the project database.

## Phase 4 student workflow

Student endpoints require a JWT for a `student` account linked to an existing
`students.student_id`. The flow is:

1. `GET /api/v1/student/profile`
2. `GET /api/v1/student/roles` and `PUT /api/v1/student/target-role`
3. `GET /api/v1/student/assessment`
4. `POST /api/v1/student/assessment/submit`
5. `GET /api/v1/student/skill-gap`, `/recommendations`, `/roadmap`, and `/readiness`
6. `POST /api/v1/student/progress` and submit a later reassessment

Assessment questions come from `assessment_questions`; correct answers are not
returned by the question endpoint. Each submission creates an immutable
`assessment_attempts` record and per-skill `student_skill_scores` records.
Scores use these thresholds: `0-39 Beginner`, `40-69 Intermediate`, `70-84
Good`, and `85-100 Strong`.

For a selected job title, required skills are aggregated from the existing
normalized job observations. The personal gap is `100 - student_score`, where
existing profile skills count as `100` until an assessment score exists. Priority
is `role_demand_score * (gap / 100)`, with labels High at `>= 0.15`, Medium at
`>= 0.05`, and Low below that threshold. Readiness is the demand-weighted
average of demonstrated scores across the selected role's required skills and
is labeled `SkillBridge Readiness Score`; it is not a hiring probability.

Roadmap weeks are generated from the ranked current gaps and available
`learning_resources`. Resources are never fabricated. Missing resources return
`Learning resource not available in current dataset`. Progress is stored in
`student_progress`, and reassessment creates a new version while preserving
previous attempts.

## Phase 5 recruiter workflow

Recruiter endpoints require a JWT with role `recruiter`. Recruiter-created
openings are stored separately from imported `job_postings`, because the
20 imported job company names do not defensibly match the 20 imported company
records. A recruiter opening uses `company_display_name` and does not create or
assign an imported company ID.

Required and preferred skill input is normalized through the existing
deterministic normalization cache. Unknown skills are rejected for review;
canonical skills are never invented. Student matching uses the latest assessed
skill score. An existing profile skill without an assessment score counts as
`100`, following the Phase 4 rule.

Matching uses:

- `required_match`: arithmetic mean of demonstrated scores across required skills
- `preferred_match`: arithmetic mean across preferred skills when present
- `final_match`: `required_match` when no preferred skills exist, otherwise
	`0.80 * required_match + 0.20 * preferred_match`
- `required_skill_coverage`: required skills with score `>= 70` divided by all
	required skills

Candidates are ranked by final match score, required-skill coverage, readiness,
then student ID. Responses contain only hiring-relevant student information,
skill scores, readiness, strengths, and gaps. Passwords, tokens, answer history,
correct answers, and sensitive attributes are never returned. Shortlists are
stored as recruiter-job-student relationships.

Recruiter endpoints include `GET /api/v1/recruiter/profile`, job CRUD under
`/api/v1/recruiter/jobs`, matches under
`/api/v1/recruiter/jobs/{job_id}/matches`, match detail, and shortlist create,
remove, and list endpoints.

## Phase 6 admin intelligence

Admin dashboard endpoints require a JWT with role `admin`. They read the
persisted Phase 3 `skill_gap_analysis` results and do not recompute on every
request:

- `GET /api/v1/admin/dashboard/summary`
- `GET /api/v1/admin/dashboard/industry-demand`
- `GET /api/v1/admin/dashboard/industry-demand/{skill_id}`
- `GET /api/v1/admin/dashboard/curriculum-coverage`
- `GET /api/v1/admin/dashboard/skill-gaps`
- `GET /api/v1/admin/dashboard/skill-gaps/{skill_id}`
- `GET /api/v1/admin/dashboard/trends`
- `POST /api/v1/admin/course-outline/generate`
- `GET /api/v1/admin/course-outline/history`

Skill-gap filters support minimum demand, maximum curriculum coverage, and
canonical skill search. The existing Phase 3 formula remains authoritative:
`gap_score = demand_score * (1 - curriculum_coverage)`.

Drilldowns join actual source jobs, raw observations, and curriculum mappings.
Unavailable source URLs and dates are returned as null. The current imported
job schema has no posting-date field, so trends return `available: false` with
an insufficient-data reason rather than inventing weekly values.

Course generation retrieves source job IDs, curriculum mapping IDs, and existing
learning resources for the selected gap. It reads `ANTHROPIC_API_KEY` through
environment configuration, but returns a graceful unavailable response when
AI is not configured. A provider result must be JSON with course title, target
skill, rationale, audience, prerequisites, objectives, modules, activities,
assessment, outcomes, and resource references. Resource IDs must exist in the
retrieved evidence, and the generated outline is stored as proposed course
history, not official curriculum.

## Phase 7 frontend

The React/Vite admin dashboard lives in `frontend/`. Node.js and npm are
required locally:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` to the FastAPI `/api/v1` URL. The browser never receives
the Anthropic key. Start the backend separately with the configured JWT secret.

Frontend routes include `/login`, `/admin`, `/admin/industry-demand`,
`/admin/curriculum`, `/admin/skill-gaps`, `/admin/skill-gaps/:skillId`,
`/admin/course-generator`, and `/admin/course-history`. Dashboard values are
loaded from the admin APIs; there are no mock metrics or generated placeholder
outlines. The UI includes loading, empty, API error, unauthorized, AI-disabled,
and unavailable-source-data states.

Student routes include `/student`, `/student/profile`, `/student/target-role`,
`/student/assessment`, `/student/skill-gap`, `/student/roadmap`,
`/student/recommendations`, and `/student/readiness`. They use the Phase 4
student APIs for profile updates, target-role requirements, assessment history,
personal gaps, recommendations, roadmap resources, progress updates, and
readiness. Student routes require a JWT linked to a student record; the backend
enforces ownership and role authorization.