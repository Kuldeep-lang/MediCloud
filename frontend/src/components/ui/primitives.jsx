import { Loader2 } from 'lucide-react'
import { useId } from 'react'

import { STATUS_TONE } from '../../utils/constants'
import { initials, titleCase } from '../../utils/format'

const TONES = {
  good: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  warning: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  critical: 'bg-red-50 text-red-700 ring-red-600/20',
  brand: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  info: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  neutral: 'bg-slate-100 text-slate-600 ring-slate-500/20',
}
const DOTS = {
  good: 'bg-emerald-500',
  warning: 'bg-amber-500',
  critical: 'bg-red-500',
  brand: 'bg-brand-500',
  info: 'bg-sky-500',
  neutral: 'bg-slate-400',
}

/** Status pill: colour dot + text label (meaning never relies on colour alone). */
export function Badge({ status, tone, children }) {
  const resolved = tone ?? STATUS_TONE[status] ?? 'neutral'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ${TONES[resolved]}`}
    >
      <span className={`size-1.5 rounded-full ${DOTS[resolved]}`} aria-hidden="true" />
      {children ?? titleCase(status)}
    </span>
  )
}

export function Spinner({ className = 'size-5', label = 'Loading' }) {
  return <Loader2 className={`animate-spin text-brand-500 ${className}`} aria-label={label} />
}

/** Label + control + error/hint, wired for accessibility. */
export function Field({ label, error, hint, required, children, className = '' }) {
  const id = useId()
  const control = typeof children === 'function' ? children(id) : children
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="label">
          {label}
          {required && <span className="text-red-500"> *</span>}
        </label>
      )}
      {control}
      {error ? (
        <p className="mt-1 text-xs text-red-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          role="tab"
          type="button"
          aria-selected={value === tab.value}
          onClick={() => onChange(tab.value)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            value === tab.value
              ? 'bg-white text-brand-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          {tab.label}
          {tab.count != null && (
            <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 text-xs text-slate-600">
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Avatar({ name, size = 'size-9' }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700 ${size}`}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function DetailItem({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{children || '—'}</dd>
    </div>
  )
}
