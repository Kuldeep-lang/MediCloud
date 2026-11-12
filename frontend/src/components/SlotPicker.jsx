import { doctorsApi } from '../api/endpoints'
import { useApi } from '../hooks/useApi'
import { formatTime } from '../utils/format'
import { Spinner } from './ui/primitives'

/** Shows a doctor's bookable slots for a date, straight from the availability API. */
export function SlotPicker({ doctorId, date, value, onChange }) {
  const slots = useApi(() => doctorsApi.availability(doctorId, date), [doctorId, date], {
    enabled: Boolean(doctorId && date),
  })

  if (!doctorId || !date) return <p className="text-sm text-slate-500">Choose a doctor and date first.</p>
  if (slots.loading && !slots.data) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="size-4" /> Loading availability…
      </p>
    )
  }
  if (slots.error) return <p className="text-sm text-red-600">{slots.error}</p>
  const list = slots.data ?? []
  if (!list.length) return <p className="text-sm text-slate-500">The doctor does not work on this day.</p>
  const free = list.filter((s) => s.available).length

  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        {free} of {list.length} slots available
      </p>
      <div role="radiogroup" aria-label="Available time slots" className="grid max-h-48 grid-cols-4 gap-1.5 overflow-y-auto sm:grid-cols-6">
        {list.map((slot) => {
          const selected = value === slot.start
          return (
            <button
              key={slot.start}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={!slot.available}
              onClick={() => onChange(slot.start)}
              className={`tabular rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors ${
                selected
                  ? 'border-brand-600 bg-brand-600 text-white'
                  : slot.available
                    ? 'border-slate-200 text-slate-700 hover:border-brand-300 hover:bg-brand-50'
                    : 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300 line-through'
              }`}
            >
              {formatTime(slot.start)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
