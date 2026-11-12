import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { LoadingState } from './components/ui/feedback'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import { rolesFor } from './routes/navigation'
import { ProtectedRoute } from './routes/ProtectedRoute'

// Pages are code-split: the login screen loads without the charting library.
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const PatientsPage = lazy(() => import('./pages/PatientsPage'))
const PatientDetailPage = lazy(() => import('./pages/PatientDetailPage'))
const DoctorsPage = lazy(() => import('./pages/DoctorsPage'))
const AppointmentsPage = lazy(() => import('./pages/AppointmentsPage'))
const BedsPage = lazy(() => import('./pages/BedsPage'))
const PharmacyPage = lazy(() => import('./pages/PharmacyPage'))
const BillingPage = lazy(() => import('./pages/BillingPage'))
const MonitoringPage = lazy(() => import('./pages/MonitoringPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

const guarded = (path, Page) => (
  <ProtectedRoute roles={rolesFor(path)}>
    <Page />
  </ProtectedRoute>
)

export default function App() {
  return (
    <Suspense fallback={<LoadingState />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="patients" element={guarded('/patients', PatientsPage)} />
          <Route path="patients/:patientId" element={guarded('/patients', PatientDetailPage)} />
          <Route path="doctors" element={guarded('/doctors', DoctorsPage)} />
          <Route path="appointments" element={guarded('/appointments', AppointmentsPage)} />
          <Route path="beds" element={guarded('/beds', BedsPage)} />
          <Route path="pharmacy" element={guarded('/pharmacy', PharmacyPage)} />
          <Route path="billing" element={guarded('/billing', BillingPage)} />
          <Route path="monitoring" element={guarded('/monitoring', MonitoringPage)} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
