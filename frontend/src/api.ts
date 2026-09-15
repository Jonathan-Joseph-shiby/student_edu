import type { AdminStudent, AdminStudentDetail, AssessmentAttempt, AssessmentQuestion, CandidateMatch, CurriculumCourse, OutlineResponse, ProgressPayload, Recommendation, RecruiterJob, RecruiterJobMatchResponse, RecruiterProfile, RequiredSkill, RoadmapItem, ShortlistResponse, SkillDetail, SkillRow, SourceJob, StudentGap, StudentProfile, StudentRole, Summary, TryItResult, User } from './types'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
export class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }
export const getToken = () => localStorage.getItem('SkillBridge_token')
export const clearSession = () => localStorage.removeItem('SkillBridge_token')

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) { const body = await response.json().catch(() => ({})); if (response.status === 401) { clearSession(); if (window.location.pathname !== '/login') window.location.assign('/login') } throw new ApiError(response.status, body.detail || 'Unable to complete the request.') }
  return response.json() as Promise<T>
}
export const api = {
  register: (payload: { email: string; password: string; role: 'student'; name: string; degree: string; department: string; year: number; skills: string }) => request<User>('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (email: string, password: string) => request<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<User>('/auth/me'),
  summary: () => request<Summary>('/admin/dashboard/summary'),
  demand: () => request<{ items: SkillRow[]; total: number }>('/admin/dashboard/industry-demand?page_size=100'),
  coverage: () => request<{ items: SkillRow[]; total: number }>('/admin/dashboard/curriculum-coverage?page_size=100'),
  gaps: (query = '') => request<{ items: SkillRow[]; total: number }>(`/admin/dashboard/skill-gaps?page_size=100${query}`),
  detail: (id: number) => request<SkillDetail>(`/admin/dashboard/skill-gaps/${id}`),
  trends: () => request<{ available: boolean; reason?: string }>('/admin/dashboard/trends'),
  outline: (skill_id: number) => request<OutlineResponse>('/admin/course-outline/generate', { method: 'POST', body: JSON.stringify({ skill_id }) }),
  history: () => request<{ items: Array<Record<string, unknown>>; total: number }>('/admin/course-outline/history'),
  adminStudents: (page = 1, page_size = 20) => request<{ items: AdminStudent[]; page: number; page_size: number; total: number }>(`/admin/students?page=${page}&page_size=${page_size}`),
  adminStudent: (studentId: string) => request<AdminStudentDetail>(`/admin/students/${studentId}`),
  recompute: () => request<Record<string, unknown>>('/admin/analysis/recompute', { method: 'POST' }),
  studentProfile: () => request<StudentProfile>('/student/profile'),
  updateStudentProfile: (payload: { name?: string; experience?: string; certifications?: string }) => request<StudentProfile>('/student/profile', { method: 'PUT', body: JSON.stringify(payload) }),
  studentRoles: () => request<{ items: StudentRole[] }>('/student/roles'),
  setTargetRole: (target_role: string) => request<{ student_id: string; target_role: string; required_skills: RequiredSkill[] }>('/student/target-role', { method: 'PUT', body: JSON.stringify({ target_role }) }),
  assessment: () => request<{ items: AssessmentQuestion[]; total: number }>('/student/assessment'),
  submitAssessment: (answers: Array<{ question_id: string; answer: string }>) => request<AssessmentAttempt>('/student/assessment/submit', { method: 'POST', body: JSON.stringify({ answers }) }),
  assessmentLatest: () => request<AssessmentAttempt | null>('/student/assessment/latest'),
  assessmentHistory: () => request<{ items: AssessmentAttempt[]; total: number }>('/student/assessment/history'),
  studentGap: () => request<StudentGap>('/student/skill-gap'),
  studentReadiness: () => request<{ label: string; target_role: string | null; score: number | null }>('/student/readiness'),
  recommendations: () => request<{ items: Recommendation[] }>('/student/recommendations'),
  roadmap: () => request<{ items: Array<{ week_number: number; items: RoadmapItem[] }> }>('/student/roadmap'),
  updateProgress: (payload: { skill_id: number; resource_id: number | null; status: ProgressPayload['status']; week_number: number }) => request<Record<string, unknown>>('/student/progress', { method: 'POST', body: JSON.stringify(payload) }),
  tryIt: (mode: TryItResult['mode'], text: string, target_role?: string) => request<TryItResult>(`/try-it/${mode}`, { method: 'POST', body: JSON.stringify({ text, ...(target_role ? { target_role } : {}) }) }),
  recruiterProfile: () => request<RecruiterProfile>('/recruiter/profile'),
  recruiterJobs: () => request<{ items: RecruiterJob[]; total: number }>('/recruiter/jobs'),
  recruiterJob: (jobId: string) => request<RecruiterJob>(`/recruiter/jobs/${jobId}`),
  createRecruiterJob: (payload: { title: string; description: string; location: string; company_display_name: string; required_skills: string[]; preferred_skills?: string[]; status?: RecruiterJob['status'] }) => request<RecruiterJob>('/recruiter/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  updateRecruiterJob: (jobId: string, payload: Partial<{ title: string; description: string; location: string; company_display_name: string; required_skills: string[]; preferred_skills: string[]; status: RecruiterJob['status'] }>) => request<RecruiterJob>(`/recruiter/jobs/${jobId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteRecruiterJob: (jobId: string) => request<{ status: string; job_id: string }>(`/recruiter/jobs/${jobId}`, { method: 'DELETE' }),
  recruiterMatches: (jobId: string, params: { target_role?: string; skill_id?: number; min_match_score?: number; min_readiness?: number; page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams()
    if (params.target_role) query.set('target_role', params.target_role)
    if (params.skill_id) query.set('skill_id', String(params.skill_id))
    if (params.min_match_score !== undefined) query.set('min_match_score', String(params.min_match_score))
    if (params.min_readiness !== undefined) query.set('min_readiness', String(params.min_readiness))
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    return request<RecruiterJobMatchResponse>(`/recruiter/jobs/${jobId}/matches${query.toString() ? `?${query.toString()}` : ''}`)
  },
  recruiterMatchDetail: (jobId: string, studentId: string) => request<CandidateMatch & { student_id: string; name: string; degree: string | null; department: string | null; year: number | null; target_role: string | null; match_score: number; required_match: number | null; preferred_match: number | null; required_skill_coverage: number; readiness_score: number | null; strong_matches: Array<{ skill_id: number; skill: string; score: number }>; skill_gaps: Array<{ skill_id: number; skill: string; score: number }>; preferred_skills: Array<{ skill_id: number; skill: string; score: number }> }>(`/recruiter/jobs/${jobId}/matches/${studentId}`),
  shortlistCandidate: (jobId: string, studentId: string) => request<{ status: string; job_id: string; student_id: string }>(`/recruiter/jobs/${jobId}/shortlist/${studentId}`, { method: 'POST' }),
  removeShortlistCandidate: (jobId: string, studentId: string) => request<{ status: string; job_id: string; student_id: string }>(`/recruiter/jobs/${jobId}/shortlist/${studentId}`, { method: 'DELETE' }),
  recruiterShortlist: (jobId: string) => request<ShortlistResponse>(`/recruiter/jobs/${jobId}/shortlist`),
}