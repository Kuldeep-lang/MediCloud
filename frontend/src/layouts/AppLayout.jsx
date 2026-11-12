import { LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import { Outlet, useLocation } from 'react-router'

import { Avatar } from '../components/ui/primitives'
import { useAuth } from '../context/AuthContext'
import { NAV_ITEMS } from '../routes/navigation'
import { ROLE_LABELS } from '../utils/constants'
import { Sidebar } from './Sidebar'

export default function AppLayout() {
  const { user, logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { pathname } = useLocation()
  const section =
    NAV_ITEMS.find((item) => (item.to === '/' ? pathname === '/' : pathname.startsWith(item.to)))
      ?.label ?? 'MediCloud'

  return (
    <div className="min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/85 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="size-5" />
            </button>
            <p className="text-sm font-medium text-slate-500">{section}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-slate-800">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{ROLE_LABELS[user?.role]}</p>
            </div>
            <Avatar name={user?.full_name} />
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={logout}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
