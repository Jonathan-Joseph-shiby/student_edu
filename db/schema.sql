PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL UNIQUE,
    industry TEXT NOT NULL,
    headquarters TEXT NOT NULL,
    states TEXT NOT NULL,
    website TEXT NOT NULL,
    company_size TEXT NOT NULL,
    domains TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT
);

CREATE TABLE IF NOT EXISTS skill_aliases (
    alias_id TEXT PRIMARY KEY,
    raw_skill TEXT NOT NULL UNIQUE,
    canonical_skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    category TEXT NOT NULL,
    confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS job_postings (
    job_id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(company_id),
    source_company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    state TEXT NOT NULL,
    city TEXT NOT NULL,
    experience TEXT NOT NULL,
    degree TEXT NOT NULL,
    salary_range TEXT NOT NULL,
    job_description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_skill_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES job_postings(job_id),
    raw_skill TEXT NOT NULL,
    canonical_skill_id INTEGER REFERENCES skills(skill_id),
    skill_requirement TEXT NOT NULL CHECK (skill_requirement IN ('required', 'preferred')),
    UNIQUE(job_id, raw_skill, skill_requirement)
);

CREATE TABLE IF NOT EXISTS curricula (
    curriculum_id TEXT PRIMARY KEY,
    university TEXT NOT NULL,
    state TEXT NOT NULL,
    degree TEXT NOT NULL,
    department TEXT NOT NULL,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    course_code TEXT NOT NULL,
    course_title TEXT NOT NULL,
    syllabus TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS curriculum_skill_observations (
    mapping_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES curricula(curriculum_id),
    course_code TEXT NOT NULL,
    course_title TEXT NOT NULL,
    observed_skill TEXT NOT NULL,
    canonical_skill_id INTEGER REFERENCES skills(skill_id),
    skill_category TEXT NOT NULL,
    coverage TEXT NOT NULL,
    gap_analysis TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    degree TEXT NOT NULL,
    department TEXT NOT NULL,
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    skills TEXT NOT NULL,
    experience TEXT NOT NULL,
    certifications TEXT NOT NULL,
    assessment_score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'recruiter', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    student_id TEXT REFERENCES students(student_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_questions (
    question_id TEXT PRIMARY KEY,
    observed_skill TEXT NOT NULL,
    canonical_skill_id INTEGER REFERENCES skills(skill_id),
    difficulty TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_resources (
    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_skill TEXT NOT NULL,
    canonical_skill_id INTEGER REFERENCES skills(skill_id),
    resource_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    url TEXT NOT NULL,
    level TEXT NOT NULL,
    type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unresolved_skill_observations (
    observed_skill TEXT PRIMARY KEY,
    sources TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS student_target_roles (
    student_id TEXT PRIMARY KEY REFERENCES students(student_id),
    target_role TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    version INTEGER NOT NULL,
    total_score REAL NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, version)
);

CREATE TABLE IF NOT EXISTS assessment_answers (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL REFERENCES assessment_attempts(attempt_id),
    question_id TEXT NOT NULL REFERENCES assessment_questions(question_id),
    selected_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    UNIQUE(attempt_id, question_id)
);

CREATE TABLE IF NOT EXISTS student_skill_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    attempt_id INTEGER NOT NULL REFERENCES assessment_attempts(attempt_id),
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    level TEXT NOT NULL CHECK (level IN ('Beginner', 'Intermediate', 'Good', 'Strong')),
    UNIQUE(attempt_id, skill_id)
);

CREATE TABLE IF NOT EXISTS student_progress (
    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    resource_id INTEGER REFERENCES learning_resources(resource_id),
    status TEXT NOT NULL CHECK (status IN ('not_started', 'in_progress', 'completed')),
    week_number INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, skill_id, resource_id)
);

CREATE TABLE IF NOT EXISTS recruiter_jobs (
    job_id TEXT PRIMARY KEY,
    recruiter_user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    location TEXT NOT NULL,
    company_display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed', 'draft')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recruiter_job_skills (
    job_skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES recruiter_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    raw_skill TEXT NOT NULL,
    requirement TEXT NOT NULL CHECK (requirement IN ('required', 'preferred')),
    UNIQUE(job_id, skill_id, requirement)
);

CREATE TABLE IF NOT EXISTS recruiter_shortlists (
    job_id TEXT NOT NULL REFERENCES recruiter_jobs(job_id) ON DELETE CASCADE,
    recruiter_user_id INTEGER NOT NULL REFERENCES users(id),
    student_id TEXT NOT NULL REFERENCES students(student_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(job_id, student_id)
);

CREATE TABLE IF NOT EXISTS course_outlines (
    outline_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    course_title TEXT NOT NULL,
    outline_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_course_outline_skill ON course_outlines(skill_id, created_at DESC);

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

CREATE INDEX IF NOT EXISTS idx_job_skill_canonical ON job_skill_observations(canonical_skill_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_skill_canonical ON curriculum_skill_observations(canonical_skill_id);
CREATE INDEX IF NOT EXISTS idx_question_skill_canonical ON assessment_questions(canonical_skill_id);
CREATE INDEX IF NOT EXISTS idx_resource_skill_canonical ON learning_resources(canonical_skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_cache_status ON skill_normalization_cache(status);
CREATE INDEX IF NOT EXISTS idx_skill_gap_score ON skill_gap_analysis(gap_score DESC);
CREATE INDEX IF NOT EXISTS idx_skill_cache_status ON skill_normalization_cache(status);
CREATE INDEX IF NOT EXISTS idx_skill_gap_score ON skill_gap_analysis(gap_score DESC);
CREATE INDEX IF NOT EXISTS idx_recruiter_job_owner ON recruiter_jobs(recruiter_user_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_job_skill ON recruiter_job_skills(job_id, requirement);