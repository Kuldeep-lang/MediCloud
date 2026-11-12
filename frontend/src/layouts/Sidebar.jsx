import { Cross, X } from 'lucide-react'
import { NavLink } from 'react-router'

import { useAppInfo } from '../context/AppInfoContext'
import { useAuth } from '../context/AuthContext'
import { NAV_ITEMS } from '../routes/navigation'

export function Sidebar({ open, onClose }) {
  const { user } = useAuth()
  const info = useAppInfo()
  const items = NAV_ITEMS.filter((item) => item.roles.includes(user?.role))

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-30 bg-navy-950/50 lg:hidden" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-navy-900 text-slate-300 transition-transform lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Main navigation"
      >
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <span className="rounded-lg bg-brand-500 p-1.5 text-white">
              <Cross className="size-4" aria-hidden="true" />
            </span>
            <div>
              <p className="text-base font-semibold tracking-tight text-white">MediCloud</p>
              <p className="text-[11px] text-slate-400">Smart Hospital</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded p-1 text-slate-400 hover:text-white lg:hidden"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-500/15 text-white ring-1 ring-brand-400/30'
                    : 'text-slate-400 hover:bg-navy-800 hover:text-white'
                }`
              }
            >
              <Icon className="size-[18px]" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-navy-800 px-5 py-4 text-[11px] text-slate-500">
          <p>Synthetic data only · simulated payments</p>
          {info.version && <p className="mt-0.5">API v{info.version}</p>}
        </div>
      </aside>
    </>
  )
}
