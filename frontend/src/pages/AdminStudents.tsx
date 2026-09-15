import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, UserRound } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { AdminStudent, AdminStudentDetail } from '../types'
import { Badge, Empty, ErrorState, Loading, Metric, SectionTitle } from '../components/UI'

export function AdminStudentsPage() {
  const [items, setItems] = useState<AdminStudent[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const pageSize = 12
  const load = () => api.adminStudents(page, pageSize).then(result => { setItems(result.items); setTotal(result.total) }).catch(err => setError(err instanceof Error ? err.message : 'Unable to load students.'))
  useEffect(() => { void load() }, [page])
  if (error) return <ErrorState message={error} retry={load} />
  return <><SectionTitle eyebrow="People / Student directory" title="Students" description="A privacy-conscious view of the learners connected to SkillBridge." /><section className="panel table-panel">{!items.length ? <Loading label="Loading student records..." /> : <table><thead><tr><th>Student</th><th>Department</th><th>Year</th><th>Target role</th><th>Readiness</th><th>Skill gaps</th><th /></tr></thead><tbody>{items.map(item => <tr key={item.student_id}><td><Link className="table-link" to={`/admin/students/${item.student_id}`}><UserRound size={14} /> {item.name}</Link><small className="table-subtext">{item.student_id} · {item.degree}</small></td><td>{item.department}</td><td>{item.year}</td><td>{item.target_role ?? <Badge>Not selected</Badge>}</td><td>{item.readiness === null ? '—' : item.readiness}</td><td>{item.skill_gap_count}</td><td><Link className="icon-link" to={`/admin/students/${item.student_id}`} aria-label={`Open ${item.name}`}><ArrowRight size={15} /></Link></td></tr>)}</tbody></table>}{total > pageSize && <div className="pagination"><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {Math.ceil(total / pageSize)}</span><button className="button secondary" disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage(value => value + 1)}>Next</button></div>}</section></>
}

export function AdminStudentDetailPage() {
  const { studentId } = useParams()
  const [data, setData] = useState<AdminStudentDetail | null>(null)
  const [error, setError] = useState('')
  const load = () => studentId ? api.adminStudent(studentId).then(setData).catch(err => setError(err instanceof Error ? err.message : 'Unable to load student.')) : undefined
  useEffect(() => { void load() }, [studentId])
  if (error) return <ErrorState message={error} retry={load} />
  if (!data) return <Loading label="Loading student record..." />
  return <><Link to="/admin/students" className="back-link"><ArrowLeft size={15} /> Back to students</Link><div className="detail-head"><div><span className="eyebrow">Student / Profile and progress</span><h1>{data.profile.name}</h1><p>{data.profile.student_id} · {data.profile.degree} · {data.profile.department}</p></div><Badge tone="success">Student record</Badge></div><div className="metric-grid detail-metrics"><Metric label="Readiness" value={data.readiness === null ? '—' : data.readiness} detail={data.target_role ?? 'Target role not selected'} /><Metric label="Skill gaps" value={data.skill_gaps.length} detail="current role gaps" accent="accent-number" /><Metric label="Assessment" value={data.latest_assessment ? `${data.latest_assessment.total_score}%` : '—'} detail={data.latest_assessment ? `Attempt ${data.latest_assessment.version}` : 'Not attempted'} /><Metric label="Roadmap weeks" value={data.roadmap.length} detail="available plan" /></div><div className="two-col"><section className="panel"><SectionTitle eyebrow="Profile" title="Student context" /><div className="profile-details"><div><span>Year / semester</span><b>{data.profile.year} / {data.profile.semester}</b></div><div><span>State</span><b>{data.profile.state}</b></div><div className="full"><span>Experience</span><b>{data.profile.experience || 'Not provided'}</b></div><div className="full"><span>Certifications</span><b>{data.profile.certifications || 'Not provided'}</b></div></div></section><section className="panel"><SectionTitle eyebrow="Demonstrated skills" title="Current evidence" />{data.demonstrated_skills.length ? <div className="skill-pills">{data.demonstrated_skills.map(skill => <Badge key={skill.skill_id} tone={skill.score >= 70 ? 'success' : 'neutral'}>{skill.skill} · {Math.round(skill.score)}</Badge>)}</div> : <Empty>No demonstrated skills yet.</Empty>}</section></div><section className="panel"><SectionTitle eyebrow="Skill analysis" title="Current gaps" />{data.skill_gaps.length ? <div className="gap-cards">{data.skill_gaps.slice(0, 8).map(gap => <div className="gap-card" key={gap.skill_id}><div><Badge tone={gap.priority === 'High' ? 'danger' : 'amber'}>{gap.priority}</Badge><h3>{gap.skill}</h3></div><strong>{Math.round(gap.student_score)}</strong></div>)}</div> : <Empty>No current gaps for this student.</Empty>}</section></>
}
