import { NavLink, Outlet } from 'react-router-dom'
import { BriefcaseBusiness, CircleUserRound, FileStack, LayoutDashboard, LogOut, Menu, PlusCircle, Sparkles, Target, X } from 'lucide-react'
import { useState } from 'react'
import type { User } from '../types'

const links = [
  { to: '/recruiter', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/recruiter/jobs', label: 'My Jobs', icon: BriefcaseBusiness },
  { to: '/recruiter/jobs/new', label: 'Create Job', icon: PlusCircle },
  { to: '/recruiter/jobs/1/matches', label: 'Candidate Matches', icon: Target },
  { to: '/recruiter/jobs/1/shortlist', label: 'Shortlist', icon: FileStack },
  { to: '/recruiter/profile', label: 'Profile', icon: CircleUserRound },
]

export function RecruiterLayout({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  return <div className="shell recruiter-shell"><aside className={open ? 'sidebar open recruiter-sidebar' : 'sidebar recruiter-sidebar'}>
    <div className="brand"><div className="brand-mark">SB</div><div><strong>SkillBridge</strong><span>recruiter workspace</span></div><button className="icon-button mobile-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18} /></button></div>
    <div className="sidebar-label">Hiring pipeline</div>
    <nav>{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}><Icon size={17} /><span>{label}</span></NavLink>)}</nav>
    <div className="sidebar-footer"><div className="account"><Sparkles size={19} /><div><b>{user.email.split('@')[0]}</b><span>Recruiter</span></div></div><button className="logout" onClick={onLogout}><LogOut size={16} /> Sign out</button></div>
  </aside>
  <main className="main"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="crumb"><BriefcaseBusiness size={17} /> Recruiter workspace</div><div className="topbar-right"><span className="live-dot" /> Skill-based matching <span className="topbar-divider" /> India focus</div></header><div className="page"><Outlet /></div></main></div>
}
