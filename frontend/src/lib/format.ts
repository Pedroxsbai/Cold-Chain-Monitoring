const dateTime = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const shortDateTime = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})
const time = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
const oneDecimal = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const integer = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })
const relative = new Intl.RelativeTimeFormat('fr', { numeric: 'auto' })

export function formatDateTime(iso: string | null | undefined) {
  return iso ? dateTime.format(new Date(iso)) : '—'
}

export function formatShortDateTime(iso: string | null | undefined) {
  return iso ? shortDateTime.format(new Date(iso)) : '—'
}

export function formatTime(iso: string | null | undefined) {
  return iso ? time.format(new Date(iso)) : '—'
}

export function formatTemp(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : `${oneDecimal.format(value)} °C`
}

export function formatNumber(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : oneDecimal.format(value)
}

export function formatHumidity(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : `${integer.format(value)} %`
}

/** 75 → "1 h 15", 45 → "45 min". */
export function formatDuration(minutes: number | null | undefined) {
  if (minutes === null || minutes === undefined) return '—'
  const total = Math.max(0, Math.round(minutes))
  const hours = Math.floor(total / 60)
  const mins = total % 60
  if (!hours) return `${mins} min`
  return `${hours} h ${String(mins).padStart(2, '0')}`
}

export function relativeTime(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return 'jamais'
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const abs = Math.abs(seconds)
  if (abs < 60) return 'à l’instant'
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), 'hour')
  return relative.format(Math.round(seconds / 86400), 'day')
}

/** YYYY-MM-DD in local time, for <input type="date">. */
export function toDateInput(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function fullName(user: { first_name: string; last_name: string; email: string }) {
  return `${user.first_name} ${user.last_name}`.trim() || user.email
}
