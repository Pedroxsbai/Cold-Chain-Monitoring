import { toDateInput } from '../lib/format'

export type PeriodKey = '24h' | '7d' | '30d' | 'custom'

export interface Period {
  key: PeriodKey
  /** For the custom period, inclusive dates (YYYY-MM-DD). */
  from?: string
  to?: string
}

const PRESETS: { key: Exclude<PeriodKey, 'custom'>; label: string; hours: number }[] = [
  { key: '24h', label: '24 h', hours: 24 },
  { key: '7d', label: '7 j', hours: 24 * 7 },
  { key: '30d', label: '30 j', hours: 24 * 30 },
]

/** Query params `from` / `to` for the API.
 *
 * Rolling periods are rounded to the minute so the result (an SWR key) stays stable
 * across renders and only moves forward once a minute.
 */
export function periodQuery(period: Period): { from?: string; to?: string } {
  if (period.key === 'custom') return { from: period.from, to: period.to }
  const hours = PRESETS.find((p) => p.key === period.key)?.hours ?? 24
  const minute = Math.floor(Date.now() / 60_000) * 60_000
  return { from: new Date(minute - hours * 3_600_000).toISOString() }
}

export function PeriodPicker({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  const today = toDateInput(new Date())
  return (
    <div className="row">
      <div className="segmented" role="group" aria-label="Période">
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            type="button"
            aria-pressed={value.key === preset.key}
            onClick={() => onChange({ key: preset.key })}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={value.key === 'custom'}
          onClick={() =>
            onChange({
              key: 'custom',
              from: value.from ?? toDateInput(new Date(Date.now() - 7 * 86_400_000)),
              to: value.to ?? today,
            })
          }
        >
          Personnalisé
        </button>
      </div>
      {value.key === 'custom' ? (
        <div className="row">
          <input
            type="date"
            className="input"
            style={{ width: 'auto' }}
            aria-label="Du"
            value={value.from ?? ''}
            max={value.to ?? today}
            onChange={(e) => onChange({ ...value, from: e.target.value })}
          />
          <span className="muted">→</span>
          <input
            type="date"
            className="input"
            style={{ width: 'auto' }}
            aria-label="Au"
            value={value.to ?? ''}
            min={value.from}
            max={today}
            onChange={(e) => onChange({ ...value, to: e.target.value })}
          />
        </div>
      ) : null}
    </div>
  )
}
