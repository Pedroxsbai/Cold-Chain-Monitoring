import type { CSSProperties } from 'react'
import { formatDuration, formatNumber } from '../lib/format'

interface RangeGaugeProps {
  value: number | null | undefined
  min: number
  max: number
  tone: string
  /** Extra degrees shown on each side of the allowed band. */
  margin?: number
}

/** Horizontal scale with the allowed band and a needle at the current reading. */
export function RangeGauge({ value, min, max, tone, margin = 6 }: RangeGaugeProps) {
  const lo = Math.min(min - margin, value ?? Infinity)
  const hi = Math.max(max + margin, value ?? -Infinity)
  const pct = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <div
      className="gauge"
      role="img"
      aria-label={`Plage ${formatNumber(min)} à ${formatNumber(max)} °C${
        value == null ? '' : `, mesure ${formatNumber(value)} °C`
      }`}
    >
      <div className="gauge-track" />
      <div className="gauge-band" style={{ left: `${pct(min)}%`, width: `${pct(max) - pct(min)}%` }} />
      {value == null ? null : (
        <div
          className="gauge-needle"
          style={{ left: `${pct(value)}%`, '--tone': `var(--${tone})` } as CSSProperties}
        />
      )}
      <div className="gauge-labels" aria-hidden="true">
        <span style={{ left: `${pct(min)}%` }}>{formatNumber(min)}</span>
        <span style={{ left: `${pct(max)}%` }}>{formatNumber(max)}</span>
      </div>
    </div>
  )
}

interface ExcursionMeterProps {
  minutes: number
  limitHours: number
  big?: boolean
}

/** One cell per hour up to the limit (10 h by default), filled as the excursion grows. */
export function ExcursionMeter({ minutes, limitHours, big }: ExcursionMeterProps) {
  const hours = minutes / 60
  const remaining = Math.max(0, limitHours * 60 - minutes)
  const ratio = hours / limitHours
  const fill = ratio >= 0.8 ? 'var(--alert)' : ratio >= 0.5 ? 'var(--warn)' : 'var(--ice)'
  return (
    <div
      className={`meter${big ? ' big' : ''}`}
      style={{ '--cells': limitHours, '--fill': fill } as CSSProperties}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={limitHours * 60}
      aria-valuenow={Math.round(minutes)}
      aria-label="Durée cumulée hors plage"
    >
      <div className="meter-cells">
        {Array.from({ length: limitHours }, (_, i) => (
          <span key={i}>
            <i style={{ width: `${Math.min(1, Math.max(0, hours - i)) * 100}%` }} />
          </span>
        ))}
      </div>
      <div className="meter-legend">
        <span>Hors plage {formatDuration(minutes)}</span>
        <span>{remaining > 0 ? `reste ${formatDuration(remaining)}` : 'seuil dépassé'}</span>
      </div>
    </div>
  )
}
