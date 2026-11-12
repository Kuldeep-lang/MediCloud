import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'

import { Spinner } from './primitives'

export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-500" role="status">
      <Spinner />
      {label}
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', description, action, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-3 rounded-full bg-brand-50 p-3 text-brand-500">
        <Icon className="size-6" aria-hidden="true" />
      </span>
      <p className="text-sm font-medium text-slate-800">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center"
    >
      <span className="rounded-full bg-red-50 p-3 text-red-600">
        <AlertTriangle className="size-6" aria-hidden="true" />
      </span>
      <p className="max-w-md text-sm text-slate-700">{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" aria-hidden="true" /> Try again
        </button>
      )}
    </div>
  )
}

/** Renders loading / error / empty / content for a useApi() result. */
export function AsyncContent({ state, empty, isEmpty, children, loadingLabel }) {
  if (state.initialLoading) return <LoadingState label={loadingLabel} />
  if (state.error && !state.data) return <ErrorState message={state.error} onRetry={state.reload} />
  if (state.data && isEmpty?.(state.data)) return empty ?? <EmptyState />
  if (!state.data) return null
  // While refetching, keep the previous render visible but dimmed (no layout jump).
  return (
    <div className={state.loading ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
      {children(state.data)}
    </div>
  )
}
