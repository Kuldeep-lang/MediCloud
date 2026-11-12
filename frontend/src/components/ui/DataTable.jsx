import { ChevronLeft, ChevronRight } from 'lucide-react'

import { EmptyState } from './feedback'

/**
 * columns: [{ key, header, render?(row), className?, align? }]
 * Rows become keyboard-accessible buttons when onRowClick is given.
 */
export function DataTable({ columns, rows, onRowClick, empty, rowKey = (row) => row.id, dense }) {
  if (!rows.length) return empty ?? <EmptyState title="No records found" />
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="table-head">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={`px-4 py-3 whitespace-nowrap ${col.align === 'right' ? 'text-right' : ''} ${col.className ?? ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onRowClick(row))
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
              className={onRowClick ? 'cursor-pointer hover:bg-brand-50/50 focus:bg-brand-50/50' : ''}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-4 ${dense ? 'py-2' : 'py-3'} align-middle ${
                    col.align === 'right' ? 'tabular text-right' : ''
                  } ${col.className ?? ''}`}
                >
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Pagination({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) {
    return <p className="px-4 py-3 text-xs text-slate-500">{total} record{total === 1 ? '' : 's'}</p>
  }
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
      <p className="text-xs text-slate-500">
        Showing <span className="font-medium text-slate-700">{first}</span>–
        <span className="font-medium text-slate-700">{last}</span> of{' '}
        <span className="font-medium text-slate-700">{total}</span>
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="btn-ghost btn-sm"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="px-2 text-xs text-slate-600">
          Page {page} of {pages}
        </span>
        <button
          type="button"
          className="btn-ghost btn-sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  )
}
