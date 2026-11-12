import { BarChart3, Table2 } from 'lucide-react'
import { useState } from 'react'

import { ErrorState, LoadingState } from '../ui/feedback'

/**
 * Card wrapper for a chart with a built-in table-view twin, so every value is
 * readable without hover or colour (accessibility requirement for data viz).
 * table: { columns: [{ key, header, format? }], rows: [] }
 */
export function ChartCard({ title, subtitle, state, table, height = 260, children, action }) {
  const [showTable, setShowTable] = useState(false)
  const ready = state ? state.data && !state.initialLoading : true
  return (
    <section className="card flex flex-col p-5">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-1">
          {action}
          {table && ready && (
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setShowTable((v) => !v)}
              aria-pressed={showTable}
              aria-label={showTable ? `Show ${title} as chart` : `Show ${title} as table`}
              title={showTable ? 'Show chart' : 'Show table'}
            >
              {showTable ? <BarChart3 className="size-4" /> : <Table2 className="size-4" />}
            </button>
          )}
        </div>
      </header>
      {state?.initialLoading ? (
        <LoadingState />
      ) : state?.error && !state?.data ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : showTable && table ? (
        <div className="overflow-auto" style={{ maxHeight: height }}>
          <table className="min-w-full text-sm">
            <thead className="table-head sticky top-0">
              <tr>
                {table.columns.map((c, i) => (
                  <th key={c.key} className={`px-3 py-2 ${i ? 'text-right' : ''}`}>
                    {c.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {table.rows.map((row, r) => (
                <tr key={r}>
                  {table.columns.map((c, i) => (
                    <td key={c.key} className={`px-3 py-1.5 ${i ? 'tabular text-right' : ''}`}>
                      {c.format ? c.format(row[c.key]) : row[c.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          className={state?.loading ? 'opacity-60 transition-opacity' : 'transition-opacity'}
          style={{ height }}
        >
          {children}
        </div>
      )}
    </section>
  )
}
