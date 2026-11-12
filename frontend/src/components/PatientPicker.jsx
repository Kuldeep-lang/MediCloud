import { Search, X } from 'lucide-react'
import { useState } from 'react'

import { patientsApi } from '../api/endpoints'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { Spinner } from './ui/primitives'

/** Searchable patient selector (name, Patient ID or phone). */
export function PatientPicker({ value, onChange, id }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const term = useDebounce(query.trim(), 250)
  const results = useApi(() => patientsApi.list({ search: term, page_size: 8 }), [term], {
    enabled: open && term.length >= 2,
  })

  if (value) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50/60 px-3 py-2">
        <div className="text-sm">
          <span className="font-medium text-slate-900">{value.full_name}</span>
          <span className="ml-2 text-slate-500">{value.patient_code}</span>
        </div>
        <button
          type="button"
          className="rounded p-1 text-slate-500 hover:bg-white"
          onClick={() => onChange(null)}
          aria-label="Clear selected patient"
        >
          <X className="size-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
      <input
        id={id}
        className="input pl-9"
        placeholder="Search by name, Patient ID or phone…"
        value={query}
        autoComplete="off"
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        role="combobox"
        aria-expanded={open && term.length >= 2}
        aria-controls={id ? `${id}-list` : undefined}
      />
      {open && term.length >= 2 && (
        <ul
          id={id ? `${id}-list` : undefined}
          role="listbox"
          // In normal flow (not absolutely positioned) so a modal's scroll area can never clip it.
          className="mt-1 max-h-64 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-card"
        >
          {results.loading && (
            <li className="flex items-center gap-2 px-3 py-2 text-sm text-slate-500">
              <Spinner className="size-4" /> Searching…
            </li>
          )}
          {!results.loading && results.data?.items.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500">No matching patients</li>
          )}
          {!results.loading &&
            results.data?.items.map((p) => {
              const choose = () => {
                onChange(p)
                setQuery('')
                setOpen(false)
              }
              // The option itself is the focusable control (no nested button - valid ARIA).
              return (
                <li
                  key={p.id}
                  role="option"
                  aria-selected="false"
                  tabIndex={0}
                  onClick={choose}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), choose())}
                  className="flex cursor-pointer items-center justify-between px-3 py-2 text-sm hover:bg-brand-50 focus:bg-brand-50 focus:outline-none"
                >
                  <span className="font-medium text-slate-800">{p.full_name}</span>
                  <span className="text-xs text-slate-500">
                    {p.patient_code} · {p.age}y · {p.phone}
                  </span>
                </li>
              )
            })}
        </ul>
      )}
    </div>
  )
}
