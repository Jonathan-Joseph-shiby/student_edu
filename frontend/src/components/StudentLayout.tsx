import { NavLink, Outlet } from 'react-router-dom'
import { BookOpenCheck, Brain, CircleUserRound, ClipboardCheck, Compass, FileText, Gauge, GraduationCap, LogOut, Menu, Route, Target, X } from 'lucide-react'
import { useState } from 'react'
import type { User } from '../types'

const links = [
  { to: '/student', label: 'Overview', icon: Compass, end: true },
  { to: '/student/profile', label: 'My profile', icon: CircleUserRound },
  { to: '/student/target-role', label: 'Target role', icon: Target },
  { to: '/student/assessment', label: 'Assessment', icon: ClipboardCheck },
  { to: '/student/skill-gap', label: 'Skill gap', icon: Brain },
  { to: '/student/roadmap', label: 'Learning roadmap', icon: Route },
  { to: '/student/recommendations', label: 'Recommendations', icon: BookOpenCheck },
  { to: '/student/readiness', label: 'Readiness', icon: Gauge },
]

export function StudentLayout({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  return <div className="shell student-shell"><aside className={open ? 'sidebar open student-sidebar' : 'sidebar student-sidebar'}><div className="brand"><div className="brand-mark">SB</div><div><strong>SkillBridge</strong><span>student growth studio</span></div><button className="icon-button mobile-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18} /></button></div><div className="sidebar-label">My career path</div><nav>{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}><Icon size={17} /><span>{label}</span></NavLink>)}</nav><div className="sidebar-footer"><div className="account"><GraduationCap size={19} /><div><b>{user.student_id ?? 'Student'}</b><span>Learning account</span></div></div><button className="logout" onClick={onLogout}><LogOut size={16} /> Sign out</button></div></aside><main className="main"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="crumb"><GraduationCap size={17} /> Student workspace</div><div className="topbar-right"><span className="live-dot" /> Personal learning path <span className="topbar-divider" /> India focus</div></header><div className="page"><Outlet /></div></main></div>
}
