/// <reference types="vitest/globals" />

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

const admin = { id: 1, email: 'admin@example.test', role: 'admin', is_active: true, student_id: null, created_at: '2026-01-01' }

beforeEach(() => {
  localStorage.clear()
  window.history.pushState({}, '', '/register')
  vi.restoreAllMocks()
})

describe('Phase 10 frontend flows', () => {
  it('renders and submits student signup', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/register')) return new Response(JSON.stringify({ id: 9, email: 'new@example.test', role: 'student', is_active: true, student_id: 'S021', created_at: '2026-01-01' }), { status: 201 })
      return new Response('{}', { status: 200 })
    }))
    render(<BrowserRouter><App /></BrowserRouter>)
    expect(screen.getByRole('heading', { name: /create your workspace/i })).toBeTruthy()
    await user.type(screen.getByLabelText(/name/i), 'New Student')
    await user.type(screen.getByLabelText(/email address/i), 'new@example.test')
    await user.type(screen.getByLabelText(/^password$/i), 'StrongPassword123!')
    await user.type(screen.getByLabelText(/degree/i), 'B.Tech')
    await user.type(screen.getByLabelText(/department/i), 'Computer Science')
    await user.click(screen.getByRole('button', { name: /create student account/i }))
    await waitFor(() => expect(screen.getByText(/account created/i)).toBeTruthy())
  })

  it('shows duplicate signup errors from the API', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Email is already registered' }), { status: 409 })))
    render(<BrowserRouter><App /></BrowserRouter>)
    await user.type(screen.getByLabelText(/name/i), 'Existing Student')
    await user.type(screen.getByLabelText(/email address/i), 'existing@example.test')
    await user.type(screen.getByLabelText(/^password$/i), 'StrongPassword123!')
    await user.type(screen.getByLabelText(/degree/i), 'B.Tech')
    await user.type(screen.getByLabelText(/department/i), 'Computer Science')
    await user.click(screen.getByRole('button', { name: /create student account/i }))
    await waitFor(() => expect(screen.getByText(/already registered/i)).toBeTruthy())
  })

  it('renders the admin student list from the API', async () => {
    localStorage.setItem('SkillBridge_token', 'admin-token')
    window.history.pushState({}, '', '/admin/students')
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/auth/me')) return new Response(JSON.stringify(admin), { status: 200 })
      if (url.includes('/admin/students')) return new Response(JSON.stringify({ items: [{ student_id: 'S001', name: 'Aarav Rana', degree: 'B.Tech', department: 'Computer Science', year: 3, target_role: 'Data Analyst', readiness: 81, skill_gap_count: 2 }], page: 1, page_size: 12, total: 1 }), { status: 200 })
      return new Response('{}', { status: 200 })
    }))
    render(<BrowserRouter><App /></BrowserRouter>)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Students' })).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Aarav Rana')).toBeTruthy())
    expect(screen.getByText('Data Analyst')).toBeTruthy()
  })

  it('runs Try It Live job analysis', async () => {
    const user = userEvent.setup()
    localStorage.setItem('SkillBridge_token', 'admin-token')
    window.history.pushState({}, '', '/try-it')
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/auth/me')) return new Response(JSON.stringify(admin), { status: 200 })
      if (url.includes('/try-it/job')) return new Response(JSON.stringify({ mode: 'job', skills: [{ raw_skill: 'Python', canonical_skill_id: 1, canonical_skill: 'Python', matched_by: 'canonical_exact', confidence: 1, status: 'normalized' }], unresolved_skills: [], implications: [], target_role_comparison: null, stored_text: false }), { status: 200 })
      return new Response('{}', { status: 200 })
    }))
    render(<BrowserRouter><App /></BrowserRouter>)
    await waitFor(() => expect(screen.getByRole('heading', { name: /try it live/i })).toBeTruthy())
    await user.type(screen.getByLabelText(/job posting text/i), 'Skills: Python')
    await user.click(screen.getByRole('button', { name: /analyze text/i }))
    await waitFor(() => expect(screen.getByText(/Python\s+Â·\s+Python/)).toBeTruthy())
  })
})
