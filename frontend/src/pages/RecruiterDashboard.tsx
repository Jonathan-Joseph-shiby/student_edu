import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, BriefcaseBusiness, CheckCircle2, CircleAlert, Filter, MapPin, ShieldCheck, Star, Users, XCircle } from 'lucide-react'
import { api } from '../api'
import { Badge, Empty, ErrorState, Loading, Metric, SectionTitle } from '../components/UI'
import type { CandidateMatch, RecruiterJob, RecruiterJobMatchResponse, RecruiterProfile, ShortlistResponse } from '../types'

function formatDate(value?: string) { return value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—' }

export function RecruiterOverviewPage() {
  const [profile, setProfile] = useState<RecruiterProfile | null>(null)
  const [jobs, setJobs] = useState<RecruiterJob[]>([])
  const [error, setError] = useState('')
  const load = () => Promise.all([api.recruiterProfile(), api.recruiterJobs()]).then(([p, r]) => { setProfile(p); setJobs(r.items) }).catch(e => setError(e.message))
  useEffect(() => { void load() }, [])
  if (error) return <ErrorState message={error} retry={load} />
  if (!profile) return <Loading label="Loading recruiter overview..." />

  const activeJobs = jobs.filter(job => job.status === 'open').length

  return <>
    <SectionTitle eyebrow="Recruiter workspace" title="Hiring overview" description="Track active openings and the candidates matching your current hiring goals." />
    <div className="metric-grid">
      <Metric label="Recruiter jobs" value={jobs.length} detail="Total openings" accent="student-number" />
      <Metric label="Open jobs" value={activeJobs} detail="Currently open" accent="accent-number" />
    </div>
    <div className="student-grid">
      <section className="panel">
        <SectionTitle eyebrow="Profile" title="Recruiter account" description="This workspace is scoped to your own jobs and candidate matches." />
        <div className="profile-details">
          <div><span>Email</span><b>{profile.email}</b></div>
          <div><span>Role</span><b>{profile.role}</b></div>
          <div className="full"><span>Company note</span><b>{profile.company_note ?? 'Imported jobs are separate from recruiter-created openings.'}</b></div>
        </div>
      </section>
      <section className="panel">
        <SectionTitle eyebrow="Next action" title="Review job pipeline" description="Open a job, review matches, then shortlist the best candidate." action={<Link className="button primary" to="/recruiter/jobs">My jobs <ArrowRight size={16} /></Link>} />
        {jobs.length ? <div className="mini-roadmap">{jobs.slice(0, 3).map(job => <div className="mini-week" key={job.job_id}><span>{job.status}</span><div><b>{job.title}</b><small>{job.location}</small></div></div>)}</div> : <Empty>No recruiter jobs created yet.</Empty>}
      </section>
    </div>
  </>
}

export function RecruiterJobsPage() {
  const [jobs, setJobs] = useState<RecruiterJob[]>([])
  const [error, setError] = useState('')
  const load = () => api.recruiterJobs().then(r => setJobs(r.items)).catch(e => setError(e.message))
  useEffect(() => { void load() }, [])
  const deleteJob = async (jobId: string) => { try { await api.deleteRecruiterJob(jobId); setJobs(jobs => jobs.filter(job => job.job_id !== jobId)) } catch (e) { setError(e instanceof Error ? e.message : 'Unable to delete job.') } }
  if (error) return <ErrorState message={error} retry={load} />
  if (!jobs) return <Loading label="Loading recruiter jobs..." />

  return <>
    <SectionTitle eyebrow="My jobs" title="Openings" description="Each job is matched against real candidate readiness and skill data from the backend." action={<Link className="button primary" to="/recruiter/jobs/new">Create job <ArrowRight size={16} /></Link>} />
    {jobs.length === 0 ? <Empty>No recruiter jobs created yet.</Empty> : <div className="table-panel"><table className="data-table"><thead><tr><th>Title</th><th>Location</th><th>Status</th><th>Required skills</th><th>Preferred</th><th>Created</th><th>Actions</th></tr></thead><tbody>{jobs.map(job => <tr key={job.job_id}><td><Link to={`/recruiter/jobs/${job.job_id}`}>{job.title}</Link></td><td>{job.location}</td><td><Badge tone={job.status === 'open' ? 'success' : job.status === 'draft' ? 'amber' : 'neutral'}>{job.status}</Badge></td><td>{job.required_skills.map(skill => skill.raw_skill).join(', ') || '—'}</td><td>{job.preferred_skills.map(skill => skill.raw_skill).join(', ') || '—'}</td><td>{formatDate(job.created_at)}</td><td className="table-actions"><Link className="button secondary" to={`/recruiter/jobs/${job.job_id}`}>View</Link><button className="button danger" onClick={() => deleteJob(job.job_id)}>Delete</button></td></tr>)}</tbody></table></div>}
  </>
}

export function RecruiterJobCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ title: '', description: '', location: '', company_display_name: '', required_skills: '', preferred_skills: '', status: 'draft' as RecruiterJob['status'] })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const job = await api.createRecruiterJob({
        title: form.title,
        description: form.description,
        location: form.location,
        company_display_name: form.company_display_name,
        required_skills: form.required_skills.split(',').map(item => item.trim()).filter(Boolean),
        preferred_skills: form.preferred_skills.split(',').map(item => item.trim()).filter(Boolean),
        status: form.status,
      })
      navigate(`/recruiter/jobs/${job.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to create job opening.')
    } finally { setSaving(false) }
  }
  return <>
    <SectionTitle eyebrow="Create job" title="New opening" description="Create a recruiter-owned opening and let the backend normalize the skills before matching candidates." />
    <section className="panel form-panel"><form className="profile-form" onSubmit={submit}>{error && <div className="form-error"><CircleAlert size={16} /> {error}</div>}<label>Job title<input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required /></label><label>Description<textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required /></label><label>Location<input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} required /></label><label>Company display name<input value={form.company_display_name} onChange={e => setForm({ ...form, company_display_name: e.target.value })} required /></label><label>Required skills<input value={form.required_skills} onChange={e => setForm({ ...form, required_skills: e.target.value })} placeholder="Python, Excel, SQL" required /></label><label>Preferred skills<input value={form.preferred_skills} onChange={e => setForm({ ...form, preferred_skills: e.target.value })} placeholder="Tableau, Power BI" /></label><label>Status<select value={form.status} onChange={e => setForm({ ...form, status: e.target.value as RecruiterJob['status'] })}><option value="draft">Draft</option><option value="open">Open</option><option value="closed">Closed</option></select></label><div className="form-actions"><button className="button primary" disabled={saving}>{saving ? 'Creating...' : 'Create job'}</button></div></form></section>
  </>
}

export function RecruiterJobDetailPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState<RecruiterJob | null>(null)
  const [error, setError] = useState('')
  const load = () => api.recruiterJob(jobId ?? '').then(setJob).catch(e => setError(e.message))
  useEffect(() => { if (jobId) void load() }, [jobId])
  if (!jobId) return <ErrorState message="Job id is missing." />
  if (error) return <ErrorState message={error} retry={load} />
  if (!job) return <Loading label="Loading job details..." />

  return <>
    <SectionTitle eyebrow="Job detail" title={job.title} description={job.description} action={<button className="button primary" onClick={() => navigate(`/recruiter/jobs/${job.job_id}/matches`)}>Find Matching Candidates <ArrowRight size={16} /></button>} />
    <div className="student-grid">
      <section className="panel">
        <div className="profile-details">
          <div><span>Location</span><b>{job.location}</b></div>
          <div><span>Status</span><b>{job.status}</b></div>
          <div><span>Company</span><b>{job.company_display_name}</b></div>
          <div><span>Created</span><b>{formatDate(job.created_at)}</b></div>
        </div>
      </section>
      <section className="panel"><SectionTitle eyebrow="Required skills" title="Skill fit" description="Normalized through the same backend workflow as job creation." />{job.required_skills.length ? <div className="skill-pills">{job.required_skills.map(skill => <Badge key={skill.skill_id}>{skill.raw_skill}</Badge>)}</div> : <Empty>No required skills.</Empty>}<SectionTitle eyebrow="Preferred skills" title="Nice-to-have" />{job.preferred_skills.length ? <div className="skill-pills">{job.preferred_skills.map(skill => <Badge key={skill.skill_id} tone="amber">{skill.raw_skill}</Badge>)}</div> : <Empty>No preferred skills.</Empty>}</section>
    </div>
  </>
}

export function RecruiterMatchesPage() {
  const { jobId } = useParams()
  const [rows, setRows] = useState<CandidateMatch[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize] = useState(20)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ min_match_score: '', min_readiness: '', target_role: '', skill: '' })
  const load = () => api.recruiterMatches(jobId ?? '', { page, page_size: pageSize, min_match_score: filters.min_match_score ? Number(filters.min_match_score) : undefined, min_readiness: filters.min_readiness ? Number(filters.min_readiness) : undefined }).then((r: RecruiterJobMatchResponse) => { setRows(r.items); setTotal(r.total) }).catch(e => setError(e.message))
  useEffect(() => { if (jobId) void load() }, [jobId, page, filters.min_match_score, filters.min_readiness])
  if (error) return <ErrorState message={error} retry={load} />
  if (!jobId) return <ErrorState message="Job id is missing." />

  return <>
    <SectionTitle eyebrow="Candidate matches" title="Ranked matches" description="Scores are sourced from the backend’s recruiter matching formula and filtered server-side where supported." />
    <section className="panel filter-panel"><div className="toolbar"><label>Min match score<input value={filters.min_match_score} onChange={e => { setFilters({ ...filters, min_match_score: e.target.value }); setPage(1) }} type="number" min="0" max="100" /></label><label>Min readiness<input value={filters.min_readiness} onChange={e => { setFilters({ ...filters, min_readiness: e.target.value }); setPage(1) }} type="number" min="0" max="100" /></label><button className="button secondary" onClick={() => { setFilters({ min_match_score: '', min_readiness: '', target_role: '', skill: '' }); setPage(1) }}>Reset</button></div></section>
    {rows.length === 0 ? <Empty>No matching candidates found.</Empty> : <div className="table-panel"><table className="data-table"><thead><tr><th>Rank</th><th>Candidate</th><th>Match</th><th>Coverage</th><th>Readiness</th><th>Strong matches</th><th>Skill gaps</th><th>Action</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.student_id}><td>#{index + 1 + (page - 1) * pageSize}</td><td><div><b>{row.name}</b><small>{row.degree ?? '—'} · {row.department ?? '—'}</small></div></td><td><b>{row.match_score}%</b><small>{row.required_match ?? 0}% required</small></td><td>{Math.round((row.required_skill_coverage || 0) * 100)}%</td><td>{row.readiness_score ?? '—'}</td><td>{row.strong_matches.slice(0, 2).map(skill => skill.skill).join(', ') || '—'}</td><td>{row.skill_gaps.slice(0, 2).map(skill => skill.skill).join(', ') || '—'}</td><td><Link className="button secondary" to={`/recruiter/jobs/${jobId}/matches/${row.student_id}`}>View</Link></td></tr>)}</tbody></table></div>}
    <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(total / pageSize))}</span><button disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage(p => p + 1)}>Next</button></div>
  </>
}

export function RecruiterMatchDetailPage() {
  const { jobId, studentId } = useParams()
  const [candidate, setCandidate] = useState<CandidateMatch | null>(null)
  const [error, setError] = useState('')
  const [shortlisted, setShortlisted] = useState(false)
  const [saved, setSaved] = useState(false)
  const load = () => { if (!jobId || !studentId) return; api.recruiterMatchDetail(jobId, studentId).then(setCandidate).catch(e => setError(e.message)) }
  useEffect(() => { load() }, [jobId, studentId])
  const shortlist = async () => { if (!jobId || !studentId) return; try { await api.shortlistCandidate(jobId, studentId); setSaved(true); setShortlisted(true) } catch (e) { setError(e instanceof Error ? e.message : 'Unable to shortlist candidate.') } }
  if (error) return <ErrorState message={error} retry={load} />
  if (!candidate) return <Loading label="Loading candidate detail..." />

  return <>
    <SectionTitle eyebrow="Candidate detail" title={candidate.name} description={candidate.degree ?? 'Candidate'} action={<button className="button primary" onClick={shortlist}>{shortlisted ? 'Shortlisted' : 'Shortlist candidate'}</button>} />
    {saved && <div className="success-banner compact"><CheckCircle2 size={15} /> Candidate shortlisted.</div>}
    <div className="student-grid">
      <section className="panel">
        <div className="profile-details">
          <div><span>Target role</span><b>{candidate.target_role ?? '—'}</b></div>
          <div><span>Readiness</span><b>{candidate.readiness_score ?? '—'}</b></div>
          <div><span>Required coverage</span><b>{Math.round((candidate.required_skill_coverage || 0) * 100)}%</b></div>
          <div><span>Match score</span><b>{candidate.match_score}%</b></div>
        </div>
      </section>
      <section className="panel">
        <SectionTitle eyebrow="Match explanation" title={`${candidate.match_score}% match`} description="The exact values below come from the backend match response." />
        <div className="insight-strip">
          <div><span className="eyebrow">Strong matches</span>{candidate.strong_matches.length ? candidate.strong_matches.map(skill => <div key={skill.skill_id}><CheckCircle2 size={14} /> {skill.skill} — {skill.score}</div>) : <span>—</span>}</div>
          <div><span className="eyebrow">Skill gaps</span>{candidate.skill_gaps.length ? candidate.skill_gaps.map(skill => <div key={skill.skill_id}><XCircle size={14} /> {skill.skill} — {skill.score}</div>) : <span>—</span>}</div>
          <div><span className="eyebrow">Required skill coverage</span><b>{Math.round((candidate.required_skill_coverage || 0) * 100)} / 100</b></div>
        </div>
      </section>
    </div>
    <section className="panel"><SectionTitle eyebrow="Skill comparison" title="Required skill fit" description="Candidate view is based on the backend’s real skill-by-skill scoring." />
      <div className="table-panel"><table className="data-table"><thead><tr><th>Skill</th><th>Required</th><th>Student score</th><th>Match</th><th>Status</th></tr></thead><tbody>{candidate.strong_matches.map(skill => <tr key={skill.skill_id}><td>{skill.skill}</td><td>Required</td><td>{skill.score}</td><td>{skill.score >= 70 ? 'Strong' : 'Moderate'}</td><td><Badge tone="success">Strong match</Badge></td></tr>)}{candidate.skill_gaps.map(skill => <tr key={skill.skill_id}><td>{skill.skill}</td><td>Required</td><td>{skill.score}</td><td>{skill.score}</td><td><Badge tone="danger">Gap</Badge></td></tr>)}{candidate.preferred_skills.map(skill => <tr key={skill.skill_id}><td>{skill.skill}</td><td>Preferred</td><td>{skill.score}</td><td>{skill.score}</td><td><Badge tone="amber">Preferred</Badge></td></tr>)}</tbody></table></div>
    </section>
  </>
}

export function RecruiterShortlistPage() {
  const { jobId } = useParams()
  const [items, setItems] = useState<ShortlistResponse['items']>([])
  const [error, setError] = useState('')
  const load = () => { if (!jobId) return; api.recruiterShortlist(jobId).then(r => setItems(r.items)).catch(e => setError(e.message)) }
  useEffect(() => { load() }, [jobId])
  if (error) return <ErrorState message={error} retry={load} />
  return <>
    <SectionTitle eyebrow="Shortlist" title="Selected candidates" description="Only candidates explicitly shortlisted for this job are shown here." />
    {items.length === 0 ? <Empty>No candidates shortlisted yet.</Empty> : <div className="table-panel"><table className="data-table"><thead><tr><th>Candidate</th><th>Degree</th><th>Department</th><th>Year</th><th>Added</th><th>Action</th></tr></thead><tbody>{items.map(item => <tr key={item.student_id}><td>{item.name}</td><td>{item.degree ?? '—'}</td><td>{item.department ?? '—'}</td><td>{item.year ?? '—'}</td><td>{formatDate(item.created_at)}</td><td><button className="button secondary" onClick={async () => { if (!jobId) return; await api.removeShortlistCandidate(jobId, item.student_id); load() }}>Remove</button></td></tr>)}</tbody></table></div>}
  </>
}
