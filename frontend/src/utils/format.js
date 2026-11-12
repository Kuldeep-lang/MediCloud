// Formatting helpers. Currency and time zone come from GET /api/v1/system/info.
const config = { currency: 'INR', timeZone: 'Asia/Kolkata', locale: 'en-IN' }

export function configureFormatting({ currency, timezone } = {}) {
  if (currency) config.currency = currency
  if (timezone) config.timeZone = timezone
}

export const getTimeZone = () => config.timeZone

export function formatCurrency(value, { compact = false } = {}) {
  return new Intl.NumberFormat(config.locale, {
    style: 'currency',
    currency: config.currency,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 2,
  }).format(Number(value ?? 0))
}

export const formatNumber = (value) => new Intl.NumberFormat(config.locale).format(Number(value ?? 0))

function fmt(value, options) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(config.locale, { timeZone: config.timeZone, ...options }).format(
    new Date(value),
  )
}

export const formatDate = (iso) => fmt(iso, { day: '2-digit', month: 'short', year: 'numeric' })
export const formatDateTime = (iso) =>
  fmt(iso, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
export const formatTime = (iso) => fmt(iso, { hour: '2-digit', minute: '2-digit', hour12: false })

/** Calendar dates (YYYY-MM-DD) carry no time zone - format them as-is. */
export function formatDay(isoDate, options = { day: '2-digit', month: 'short' }) {
  if (!isoDate) return '—'
  return new Intl.DateTimeFormat(config.locale, { timeZone: 'UTC', ...options }).format(
    new Date(`${isoDate}T00:00:00Z`),
  )
}

export function formatMonth(yyyyMm) {
  return formatDay(`${yyyyMm}-01`, { month: 'short', year: 'numeric' })
}

/** Today's date (YYYY-MM-DD) in the hospital's time zone. */
export function todayLocal(offsetDays = 0) {
  const date = new Date(Date.now() + offsetDays * 86_400_000)
  return new Intl.DateTimeFormat('en-CA', { timeZone: config.timeZone }).format(date)
}

/** Calendar date (YYYY-MM-DD) of a timestamp, in the hospital's time zone. */
export function localDateOf(iso) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: config.timeZone }).format(new Date(iso))
}

export function titleCase(value) {
  if (!value) return ''
  const text = String(value).replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function initials(name = '') {
  return name
    .replace(/^Dr\.\s*/, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}m`
  return `${m}m ${s % 60}s`
}
