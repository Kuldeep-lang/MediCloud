/** Helpers for doctor schedule blocks (times arrive from the API as HH:MM:SS). */
export const hhmm = (t) => (t ? String(t).slice(0, 5) : '')

export const WEEKDAY_PRESET = [0, 1, 2, 3, 4].map((day) => ({
  day_of_week: day,
  start_time: '09:00',
  end_time: '17:00',
  slot_minutes: 20,
}))

export const toApiBlocks = (blocks) =>
  blocks.map((b) => ({ ...b, start_time: hhmm(b.start_time), end_time: hhmm(b.end_time) }))
