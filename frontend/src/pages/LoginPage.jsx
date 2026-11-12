import { Activity, Cloud, Cross, Lock, Mail, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { errorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { DEMO_ACCOUNTS } from '../utils/constants'

const HIGHLIGHTS = [
  { icon: Cloud, text: 'Containerised and orchestrated on Kubernetes' },
  { icon: Activity, text: 'Live metrics with Prometheus and Grafana' },
  { icon: ShieldCheck, text: 'Role-based access with JWT and Argon2id' },
]

export default function LoginPage() {
  const { login, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from && location.state.from !== '/login' ? location.state.from : '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (status === 'authenticated') return <Navigate to={from} replace />

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Unable to sign in.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-navy-900 p-12 text-white lg:flex">
        <div className="absolute -top-24 -right-24 size-96 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <span className="rounded-xl bg-brand-500 p-2">
            <Cross className="size-5" aria-hidden="true" />
          </span>
          <span className="text-xl font-semibold tracking-tight">MediCloud</span>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-4xl leading-tight font-semibold tracking-tight">
            Smart hospital management, built cloud-native.
          </h1>
          <p className="mt-4 text-slate-300">
            Patients, doctors, appointments, beds, pharmacy and billing in one secure platform.
          </p>
          <ul className="mt-8 space-y-3">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-sm text-slate-200">
                <span className="rounded-lg bg-white/10 p-1.5">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-400">
          Academic demonstration · all patient data is synthetic
        </p>
      </section>

      <section className="flex items-center justify-center bg-page px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="rounded-lg bg-brand-600 p-1.5 text-white">
              <Cross className="size-4" aria-hidden="true" />
            </span>
            <span className="text-lg font-semibold text-slate-900">MediCloud</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Welcome back</h2>
          <p className="mt-1 text-sm text-slate-500">Sign in with your staff account.</p>

          <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
            <label className="block">
              <span className="label">Email</span>
              <span className="relative block">
                <Mail className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
                <input
                  type="email"
                  className="input pl-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  required
                />
              </span>
            </label>
            <label className="block">
              <span className="label">Password</span>
              <span className="relative block">
                <Lock className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
                <input
                  type="password"
                  className="input pl-9"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </span>
            </label>
            <button type="submit" className="btn-primary w-full py-2.5" disabled={busy || !email || !password}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-600">Demo accounts</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Password is the <code className="rounded bg-slate-100 px-1">SEED_DEMO_PASSWORD</code> from
              your environment.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-left text-xs hover:border-brand-300 hover:bg-brand-50"
                  onClick={() => setEmail(account.email)}
                >
                  <span className="block font-medium text-slate-700">{account.role}</span>
                  <span className="block truncate text-slate-500">{account.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
