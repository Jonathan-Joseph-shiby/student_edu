import { useState } from 'react'
import { FlaskConical, Search, Sparkles } from 'lucide-react'
import { api } from '../api'
import type { TryItResult } from '../types'
import { Badge, Empty, ErrorState, Loading, SectionTitle } from '../components/UI'

const modes: Array<{ value: TryItResult['mode']; label: string; prompt: string }> = [
  { value: 'job', label: 'Job posting', prompt: 'Paste a job posting with a skills or technologies section.' },
  { value: 'resume', label: 'Resume', prompt: 'Paste a resume and optionally compare it with a target role.' },
  { value: 'syllabus', label: 'Syllabus', prompt: 'Paste syllabus subjects or a curriculum skills section.' },
]

export function TryItPage() {
  const [mode, setMode] = useState<TryItResult['mode']>('job')
  const [text, setText] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [result, setResult] = useState<TryItResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const current = modes.find(item => item.value === mode)!
  async function submit() {
    if (!text.trim()) { setError('Paste some text to analyze.'); return }
    setBusy(true); setError(''); setResult(null)
    try { setResult(await api.tryIt(mode, text, mode === 'resume' ? targetRole : undefined)) } catch (err) { setError(err instanceof Error ? err.message : 'Unable to analyze this text.') } finally { setBusy(false) }
  }
  return <><SectionTitle eyebrow="Live analysis / Canonical skills" title="Try It Live" description="Paste a real-world artifact and see the same normalization layer used by SkillBridge." action={<div className="tryit-mark"><FlaskConical size={18} /> No document storage</div>} /><section className="panel tryit-panel"><div className="mode-tabs">{modes.map(item => <button key={item.value} className={mode === item.value ? 'mode-tab active' : 'mode-tab'} onClick={() => { setMode(item.value); setResult(null); setError('') }}>{item.label}</button>)}</div><p className="muted">{current.prompt}</p><textarea aria-label={`${current.label} text`} value={text} onChange={event => setText(event.target.value)} maxLength={12000} placeholder="Paste text here..." />{mode === 'resume' && <label>Compare with target role <input value={targetRole} onChange={event => setTargetRole(event.target.value)} placeholder="Optional exact job title" /></label>}{error && <div className="form-error"><Search size={16} />{error}</div>}<div className="tryit-actions"><span>{text.length} / 12000 characters</span><button className="button primary" onClick={submit} disabled={busy}>{busy ? 'Analyzing...' : <>Analyze text <Sparkles size={16} /></>}</button></div></section>{busy && <Loading label="Normalizing against the canonical skill taxonomy..." />}{result && <section className="tryit-results"><section className="panel"><SectionTitle eyebrow="Detected and normalized" title={`${result.skills.length} canonical skill${result.skills.length === 1 ? '' : 's'}`} />{result.skills.length ? <div className="skill-pills">{result.skills.map(skill => <Badge key={`${skill.raw_skill}-${skill.canonical_skill_id}`} tone="success">{skill.canonical_skill} Â· {skill.raw_skill}</Badge>)}</div> : <Empty>No canonical skills detected.</Empty>}{result.unresolved_skills.length > 0 && <div className="tryit-unresolved"><h3>Unresolved terms</h3><div className="skill-pills">{result.unresolved_skills.map(skill => <Badge key={skill.raw_skill} tone="amber">{skill.raw_skill}</Badge>)}</div></div>}</section><section className="panel"><SectionTitle eyebrow="Implications" title="Industry and curriculum signal" />{result.implications.length ? <div className="implication-list">{result.implications.map(item => <div key={item.skill_id}><span>{item.skill}</span><b>{Math.round(item.demand_score * 100)}% demand</b><small>{item.curriculum_coverage ? 'Curriculum coverage exists' : 'No curriculum coverage'} Â· gap score {item.gap_score.toFixed(2)}</small></div>)}</div> : <Empty>No persisted gap analysis is available for these skills.</Empty>}{result.target_role_comparison && <div className="comparison"><h3>{result.target_role_comparison.target_role}</h3><p>{result.target_role_comparison.matched_skills.length} required skills matched. {result.target_role_comparison.missing_skills.length} remain to explore.</p></div>}</section></section>}</>
}
