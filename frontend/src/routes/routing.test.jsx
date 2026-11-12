import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Sidebar } from '../layouts/Sidebar'
import { USERS } from '../test/server'
import { renderWithProviders, signInAs } from '../test/utils'
import { rolesFor } from './navigation'
import { ProtectedRoute } from './ProtectedRoute'

describe('ProtectedRoute', () => {
  it('redirects anonymous visitors to the login page', async () => {
    renderWithProviders(<ProtectedRoute><p>Secret</p></ProtectedRoute>)
    expect(await screen.findByText('Login screen')).toBeInTheDocument()
    expect(screen.queryByText('Secret')).not.toBeInTheDocument()
  })

  it('blocks roles that are not allowed', async () => {
    signInAs(USERS.pharmacist)
    renderWithProviders(<ProtectedRoute roles={rolesFor('/billing')}><p>Billing</p></ProtectedRoute>)
    expect(await screen.findByText('Access restricted')).toBeInTheDocument()
    expect(screen.queryByText('Billing')).not.toBeInTheDocument()
  })

  it('renders the page for allowed roles', async () => {
    signInAs(USERS.receptionist)
    renderWithProviders(<ProtectedRoute roles={rolesFor('/billing')}><p>Billing</p></ProtectedRoute>)
    expect(await screen.findByText('Billing')).toBeInTheDocument()
  })
})

describe('Sidebar navigation', () => {
  const linksFor = async (user) => {
    signInAs(user)
    renderWithProviders(<Sidebar open onClose={() => {}} />)
    await screen.findByRole('link', { name: 'Dashboard' })
    return screen.getAllByRole('link').map((a) => a.textContent)
  }

  it('shows admins every module including monitoring', async () => {
    expect(await linksFor(USERS.admin)).toEqual([
      'Dashboard', 'Patients', 'Doctors', 'Appointments', 'Beds & Wards', 'Pharmacy', 'Billing', 'System Monitoring',
    ])
  })

  it('shows pharmacists only their modules', async () => {
    expect(await linksFor(USERS.pharmacist)).toEqual(['Dashboard', 'Patients', 'Pharmacy'])
  })

  it('hides billing and monitoring from doctors', async () => {
    const links = await linksFor(USERS.doctor)
    expect(links).not.toContain('Billing')
    expect(links).not.toContain('System Monitoring')
    expect(links).toContain('Appointments')
  })
})
