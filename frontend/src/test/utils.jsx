import { render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router'

import { tokenStore } from '../api/client'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import { API, server } from './server'

/** Pretend `user` is signed in: store a token and answer /auth/me with them. */
export function signInAs(user) {
  tokenStore.set('test-token')
  server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(user)))
}

/** Render with router + auth + toasts. `path` lets route params work. */
export function renderWithProviders(ui, { route = '/', path = '*' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path={path} element={ui} />
            <Route path="/login" element={<p>Login screen</p>} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}
