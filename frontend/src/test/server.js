import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

export const API = 'http://localhost:3000/api/v1'

export const USERS = {
  admin: { id: 1, email: 'admin@medicloud.demo', full_name: 'Priya Nair', role: 'admin', is_active: true, doctor_id: null, created_at: '2026-01-01T00:00:00Z' },
  receptionist: { id: 2, email: 'reception@medicloud.demo', full_name: 'Kavya Iyer', role: 'receptionist', is_active: true, doctor_id: null, created_at: '2026-01-01T00:00:00Z' },
  pharmacist: { id: 3, email: 'pharmacy@medicloud.demo', full_name: 'Rohan Gupta', role: 'pharmacist', is_active: true, doctor_id: null, created_at: '2026-01-01T00:00:00Z' },
  doctor: { id: 4, email: 'doctor@medicloud.demo', full_name: 'Dr. Arjun Mehta', role: 'doctor', is_active: true, doctor_id: 1, created_at: '2026-01-01T00:00:00Z' },
}

// Handlers shared by every test; individual tests override with server.use().
export const defaultHandlers = [
  http.get(`${API}/system/info`, () =>
    HttpResponse.json({ app: 'MediCloud', version: '1.0.0', environment: 'test', currency: 'INR', timezone: 'Asia/Kolkata' }),
  ),
]

export const server = setupServer(...defaultHandlers)
