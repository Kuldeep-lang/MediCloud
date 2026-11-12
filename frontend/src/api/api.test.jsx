/** API integration tests: real axios calls intercepted by MSW at the network layer. */
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import LoginPage from '../pages/LoginPage'
import PatientsPage from '../pages/PatientsPage'
import DashboardPage from '../pages/DashboardPage'
import { ProtectedRoute } from '../routes/ProtectedRoute'
import { API, server, USERS } from '../test/server'
import { renderWithProviders, signInAs } from '../test/utils'
import { errorMessage, tokenStore } from './client'
import { patientsApi } from './endpoints'

const SUMMARY = {
  total_patients: 120, total_doctors: 16, appointments_today: 35,
  beds: { total: 80, available: 45, occupied: 33, maintenance: 2 },
  icu: { total: 12, available: 4, occupied: 8, maintenance: 0 },
  active_admissions: 33, pending_prescriptions: 54, low_stock_medicines: 8,
  unpaid_invoices: 271, monthly_revenue: 247115.9,
}

function mockDashboard(summary = SUMMARY) {
  server.use(
    http.get(`${API}/dashboard/summary`, () => HttpResponse.json(summary)),
    http.get(`${API}/dashboard/admissions-trend`, () => HttpResponse.json([{ date: '2026-11-12', admissions: 3, discharges: 1 }])),
    http.get(`${API}/dashboard/appointment-stats`, () => HttpResponse.json({ by_status: [{ status: 'completed', count: 10 }], daily: [] })),
    http.get(`${API}/dashboard/department-distribution`, () => HttpResponse.json([{ department: 'Cardiology', patients: 12 }])),
    http.get(`${API}/dashboard/revenue`, () => HttpResponse.json([{ month: '2026-11', revenue: 1000 }])),
    http.get(`${API}/beds/occupancy`, () => HttpResponse.json({ overall: {}, by_ward_type: {}, wards: [] })),
    http.get(`${API}/appointments`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 6 })),
  )
}

describe('errorMessage', () => {
  it('reads FastAPI validation errors', () => {
    const err = { response: { data: { detail: [{ loc: ['body', 'date_of_birth'], msg: 'cannot be in the future' }] } } }
    expect(errorMessage(err)).toBe('date of birth: cannot be in the future')
  })
  it('explains network failures', () => {
    expect(errorMessage(new Error('Network Error'))).toMatch(/Cannot reach the server/)
  })
})

describe('authentication flow', () => {
  it('logs in, stores the token and leaves the login page', async () => {
    let body
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ access_token: 'jwt-123', token_type: 'bearer', expires_in: 3600, user: USERS.admin })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />, { route: '/login', path: '/login' })
    await user.type(screen.getByLabelText('Email'), 'admin@medicloud.demo')
    await user.type(screen.getByLabelText('Password'), 'Demo@12345')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(tokenStore.get()).toBe('jwt-123'))
    expect(body).toEqual({ email: 'admin@medicloud.demo', password: 'Demo@12345' })
  })

  it('shows the server message on bad credentials', async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 401 })))
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />, { route: '/login', path: '/login' })
    await user.type(screen.getByLabelText('Email'), 'admin@medicloud.demo')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
    expect(tokenStore.get()).toBeNull()
  })

  it('attaches the bearer token and signs out on 401', async () => {
    let authHeader
    server.use(http.get(`${API}/patients`, ({ request }) => {
      authHeader = request.headers.get('Authorization')
      return HttpResponse.json({ detail: 'Invalid or expired token' }, { status: 401 })
    }))
    signInAs(USERS.admin)
    await expect(patientsApi.list()).rejects.toBeTruthy()
    expect(authHeader).toBe('Bearer test-token')
  })
})

describe('dashboard', () => {
  it('renders KPIs from the API, including revenue for admins', async () => {
    mockDashboard()
    signInAs(USERS.admin)
    renderWithProviders(<ProtectedRoute><DashboardPage /></ProtectedRoute>)
    expect(await screen.findByText('120')).toBeInTheDocument()
    expect(screen.getByText('45 / 80')).toBeInTheDocument()
    expect(screen.getByText('Revenue this month')).toBeInTheDocument()
    expect(screen.getByText('₹2,47,115.90')).toBeInTheDocument()
  })

  it('does not show revenue to receptionists', async () => {
    const { monthly_revenue: _omit, ...withoutRevenue } = SUMMARY
    mockDashboard(withoutRevenue)
    signInAs(USERS.receptionist)
    renderWithProviders(<ProtectedRoute><DashboardPage /></ProtectedRoute>)
    expect(await screen.findByText('Unpaid invoices')).toBeInTheDocument()
    expect(screen.queryByText('Revenue this month')).not.toBeInTheDocument()
  })
})

describe('patients page', () => {
  it('lists patients and sends the search term to the API', async () => {
    const searches = []
    server.use(http.get(`${API}/patients`, ({ request }) => {
      const search = new URL(request.url).searchParams.get('search')
      searches.push(search)
      const items = [{ id: 7, patient_code: 'MCP-000007', full_name: search ? 'Zara Sheikh' : 'Meera Pillai', email: null, age: 41, gender: 'female', phone: '+91 9988776655', blood_group: 'B+', created_at: '2026-10-01T10:00:00Z' }]
      return HttpResponse.json({ items, total: 1, page: 1, page_size: 15 })
    }))
    signInAs(USERS.receptionist)
    const user = userEvent.setup()
    renderWithProviders(<ProtectedRoute><PatientsPage /></ProtectedRoute>)
    expect(await screen.findByText('Meera Pillai')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Register patient/ })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Search patients'), 'zara')
    expect(await screen.findByText('Zara Sheikh')).toBeInTheDocument()
    expect(searches).toContain('zara')
  })

  it('hides registration from pharmacists', async () => {
    server.use(http.get(`${API}/patients`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 15 })))
    signInAs(USERS.pharmacist)
    renderWithProviders(<ProtectedRoute><PatientsPage /></ProtectedRoute>)
    expect(await screen.findByText('No patients registered yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Register patient/ })).not.toBeInTheDocument()
  })
})
