import { Plus, Trash2 } from 'lucide-react'

import { DAYS } from '../utils/constants'
import { hhmm, WEEKDAY_PRESET } from '../utils/schedule'

/** Summarise schedule blocks as "Mon 09:00-13:00" chips. */
export function ScheduleSummary({ schedules }) {
  if (!schedules?.length) return <p className="text-xs text-slate-400">No schedule set</p>
  const byDay = {}
  schedules.forEach((s) => {
    byDay[s.day_of_week] = [...(byDay[s.day_of_week] ?? []), `${hhmm(s.start_time)}–${hhmm(s.end_time)}`]
  })
  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(byDay).map(([day, ranges]) => (
        <span key={day} className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
          <span className="font-medium">{DAYS[day].slice(0, 3)}</span> {ranges.join(', ')}
        </span>
      ))}
    </div>
  )
}

/** Editable list of weekly availability blocks. */
export function ScheduleEditor({ blocks, onChange }) {
  const update = (index, key, value) =>
    onChange(blocks.map((b, i) => (i === index ? { ...b, [key]: key === 'start_time' || key === 'end_time' ? value : Number(value) } : b)))
  const remove = (index) => onChange(blocks.filter((_, i) => i !== index))
  const add = () =>
    onChange([...blocks, { day_of_week: 0, start_time: '09:00', end_time: '13:00', slot_minutes: 20 }])

  return (
    <div className="space-y-2">
      {blocks.length === 0 && <p className="text-sm text-slate-500">No working hours yet.</p>}
      {blocks.map((block, i) => (
        <div key={i} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2">
          <select
            className="input"
            value={block.day_of_week}
            onChange={(e) => update(i, 'day_of_week', e.target.value)}
            aria-label="Day"
          >
            {DAYS.map((d, idx) => (
              <option key={d} value={idx}>
                {d}
              </option>
            ))}
          </select>
          <input type="time" className="input w-28" value={hhmm(block.start_time)} onChange={(e) => update(i, 'start_time', e.target.value)} aria-label="Start time" />
          <input type="time" className="input w-28" value={hhmm(block.end_time)} onChange={(e) => update(i, 'end_time', e.target.value)} aria-label="End time" />
          <select className="input w-24" value={block.slot_minutes} onChange={(e) => update(i, 'slot_minutes', e.target.value)} aria-label="Slot length">
            {[10, 15, 20, 30, 45, 60].map((m) => (
              <option key={m} value={m}>
                {m} min
              </option>
            ))}
          </select>
          <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => remove(i)} aria-label="Remove block">
            <Trash2 className="size-4" />
          </button>
        </div>
      ))}
      <div className="flex gap-2 pt-1">
        <button type="button" className="btn-secondary btn-sm" onClick={add}>
          <Plus className="size-3.5" aria-hidden="true" /> Add hours
        </button>
        <button type="button" className="btn-ghost btn-sm" onClick={() => onChange(WEEKDAY_PRESET)}>
          Weekdays 09:00–17:00
        </button>
      </div>
    </div>
  )
}
