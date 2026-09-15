import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError, clearSession, getToken } from './api'
import type { User } from './types'
import { AdminLayout } from './components/AdminLayout'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Overview } from './pages/Overview'
import { Demand } from './pages/Demand'
import { Coverage } from './pages/Coverage'
import { Gaps } from './pages/Gaps'
import { GapDetail } from './pages/GapDetail'
import { CourseGenerator } from './pages/CourseGenerator'
import { History } from './pages/History'
import { StudentLayout } from './components/StudentLayout'
import { StudentOverview, StudentProfilePage, TargetRolePage } from './pages/StudentCore'
import { AssessmentPage } from './pages/StudentAssessment'
import { StudentGapPage, ReadinessPage } from './pages/StudentInsights'
import { RoadmapPage, RecommendationsPage } from './pages/StudentLearning'
import { RecruiterLayout } from './components/RecruiterLayout'
import { AdminStudentDetailPage, AdminStudentsPage } from './pages/AdminStudents'
import { TryItPage } from './pages/TryIt'
import { RecruiterOverviewPage, RecruiterJobsPage, RecruiterJobCreatePage, RecruiterJobDetailPage, RecruiterMatchesPage, RecruiterMatchDetailPage, RecruiterShortlistPage } from './pages/RecruiterDashboard'

function Guard({ user, children }: { user: User | null; children: ReactNode }) {
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== 'admin') return <Navigate to="/login" replace />
  return children
}

function RoleGuard({ user, role, children }: { user: User | null; role: User['role']; children: ReactNode }) {
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : user.role === 'student' ? '/student' : '/login'} replace />
  return children
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(Boolean(getToken()))
  const navigate = useNavigate()
  useEffect(() => { if (!getToken()) return; api.me().then(setUser).catch(() => { clearSession(); navigate('/login') }).finally(() => setBooting(false)) }, [navigate])
  if (booting) return <div className="full-state"><span className="spinner" />Loading SkillBridge...</div>
  return <Routes>
    <Route path="/login" element={<Login onLoggedIn={setUser} />} />
    <Route path="/register" element={<Register />} />
    <Route path="/try-it" element={user ? <TryItPage /> : <Navigate to="/login" replace />} />
    <Route path="/" element={<Navigate to={user ? user.role === 'admin' ? '/admin' : user.role === 'student' ? '/student' : user.role === 'recruiter' ? '/recruiter' : '/login' : '/login'} replace />} />
    <Route path="/admin" element={<Guard user={user}><AdminLayout user={user!} onLogout={() => { clearSession(); setUser(null); navigate('/login') }} /></Guard>}>
      <Route index element={<Overview />} />
      <Route path="industry-demand" element={<Demand />} />
      <Route path="curriculum" element={<Coverage />} />
      <Route path="skill-gaps" element={<Gaps />} />
      <Route path="skill-gaps/:skillId" element={<GapDetail />} />
      <Route path="course-generator" element={<CourseGenerator />} />
      <Route path="course-history" element={<History />} />
      <Route path="students" element={<AdminStudentsPage />} />
      <Route path="students/:studentId" element={<AdminStudentDetailPage />} />
    </Route>
    <Route path="/student" element={<RoleGuard user={user} role="student"><StudentLayout user={user!} onLogout={() => { clearSession(); setUser(null); navigate('/login') }} /></RoleGuard>}>
      <Route index element={<StudentOverview />} />
      <Route path="profile" element={<StudentProfilePage />} />
      <Route path="target-role" element={<TargetRolePage />} />
      <Route path="assessment" element={<AssessmentPage />} />
      <Route path="skill-gap" element={<StudentGapPage />} />
      <Route path="roadmap" element={<RoadmapPage />} />
      <Route path="recommendations" element={<RecommendationsPage />} />
      <Route path="readiness" element={<ReadinessPage />} />
    </Route>
    <Route path="/recruiter" element={<RoleGuard user={user} role="recruiter"><RecruiterLayout user={user!} onLogout={() => { clearSession(); setUser(null); navigate('/login') }} /></RoleGuard>}>
      <Route index element={<RecruiterOverviewPage />} />
      <Route path="profile" element={<RecruiterOverviewPage />} />
      <Route path="jobs" element={<RecruiterJobsPage />} />
      <Route path="jobs/new" element={<RecruiterJobCreatePage />} />
      <Route path="jobs/:jobId" element={<RecruiterJobDetailPage />} />
      <Route path="jobs/:jobId/matches" element={<RecruiterMatchesPage />} />
      <Route path="jobs/:jobId/matches/:studentId" element={<RecruiterMatchDetailPage />} />
      <Route path="jobs/:jobId/shortlist" element={<RecruiterShortlistPage />} />
    </Route>
    <Route path="*" element={<Navigate to={user ? user.role === 'admin' ? '/admin' : user.role === 'student' ? '/student' : user.role === 'recruiter' ? '/recruiter' : '/login' : '/login'} replace />} />
  </Routes>
}

export function friendlyError(error: unknown) { return error instanceof ApiError && error.status === 403 ? 'Access denied for this account.' : error instanceof Error ? error.message : 'Something went wrong. Please try again.' }