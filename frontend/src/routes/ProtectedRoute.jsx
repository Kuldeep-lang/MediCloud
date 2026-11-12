import { Navigate, useLocation } from 'react-router'

import { LoadingState } from '../components/ui/feedback'
import { useAuth } from '../context/AuthContext'
import ForbiddenPage from '../pages/ForbiddenPage'

/** Requires a signed-in user, optionally with one of `roles`. */
export function ProtectedRoute({ roles, children }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <LoadingState label="Restoring your session…" />
  if (status !== 'authenticated') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (roles && !roles.includes(user.role)) return <ForbiddenPage />
  return children
}
