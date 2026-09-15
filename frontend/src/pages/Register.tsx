import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, LockKeyhole, Radar } from 'lucide-react'
import { api } from '../api'

export function Register() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', degree: '', department: '', year: '1', skills: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }))
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.register({ ...form, year: Number(form.year), role: 'student' })
      navigate('/login', { state: { message: 'Account created. Sign in to begin your SkillBridge path.' } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create your account.')
    } finally {
      setBusy(false)
    }
  }
  return <div className="login-page"><div className="login-aside"><div className="brand light"><div className="brand-mark">IP</div><div><strong>SkillBridge</strong><span>workforce intelligence</span></div></div><div className="login-message"><span className="eyebrow">A clearer route into the market</span><h1>Build your<br /><em>next signal.</em></h1><p>Start with your context. SkillBridge will connect it to real demand, skill gaps, and a practical learning path.</p></div><div className="login-aside-foot"><span>INDIA / 01</span><span>STUDENT ONBOARDING</span></div></div><div className="login-card-wrap"><div className="login-card register-card"><div className="mobile-logo"><Radar size={22} /> SkillBridge</div><span className="eyebrow">Student signup</span><h2>Create your workspace</h2><p className="muted">Your profile starts here. You can refine it after signing in.</p><form onSubmit={submit}><div className="form-grid"><label>Name<input value={form.name} onChange={e => update('name', e.target.value)} autoComplete="name" required /></label><label>Email address<input value={form.email} onChange={e => update('email', e.target.value)} type="email" autoComplete="email" required /></label><label>Password<input value={form.password} onChange={e => update('password', e.target.value)} type="password" minLength={8} autoComplete="new-password" required /></label><label>Year<input value={form.year} onChange={e => update('year', e.target.value)} type="number" min="1" max="10" required /></label><label>Degree<input value={form.degree} onChange={e => update('degree', e.target.value)} required /></label><label>Department<input value={form.department} onChange={e => update('department', e.target.value)} required /></label></div><label>Initial skills <span className="muted">(optional)</span><input value={form.skills} onChange={e => update('skills', e.target.value)} placeholder="Python, SQL, Excel" /></label>{error && <div className="form-error"><LockKeyhole size={16} />{error}</div>}<button className="button primary wide" disabled={busy}>{busy ? 'Creating account...' : <>Create student account <ArrowRight size={17} /></>}</button></form><p className="login-note">Already have an account? <Link className="text-link" to="/login">Sign in</Link></p></div></div></div>
}
