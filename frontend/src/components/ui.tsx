import { useId } from 'react'
import type { ReactNode } from 'react'
import { DEVICE_STATUS, FRIDGE_STATUS, INCIDENT_STATUS } from '../lib/labels'
import type { DeviceStatus, FridgeStatus, IncidentStatus } from '../lib/types'

export type Tone = 'ok' | 'alert' | 'warn' | 'off' | 'ice'

export const FRIDGE_TONE: Record<FridgeStatus, Tone> = {
  normal: 'ok',
  alert: 'alert',
  offline: 'off',
}

export const INCIDENT_TONE: Record<IncidentStatus, Tone> = {
  open: 'alert',
  acknowledged: 'warn',
  ended: 'ice',
  closed: 'off',
}

const DEVICE_TONE: Record<DeviceStatus, Tone> = { unknown: 'off', online: 'ok', offline: 'alert' }

export function Badge({ tone, pulse, children }: { tone: Tone; pulse?: boolean; children: ReactNode }) {
  return <span className={`badge tone-${tone}${pulse ? ' pulse' : ''}`}>{children}</span>
}

export function FridgeStatusBadge({ status }: { status: FridgeStatus }) {
  return (
    <Badge tone={FRIDGE_TONE[status]} pulse={status === 'alert'}>
      {FRIDGE_STATUS[status]}
    </Badge>
  )
}

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <Badge tone={INCIDENT_TONE[status]} pulse={status === 'open'}>
      {INCIDENT_STATUS[status]}
    </Badge>
  )
}

export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  return <Badge tone={DEVICE_TONE[status]}>{DEVICE_STATUS[status]}</Badge>
}

export function LevelChip({ level }: { level: number }) {
  return <span className="level-chip">N{level}</span>
}

export function Spinner({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <div className="spinner" />
      <span className="visually-hidden">{label}</span>
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children ? <span>{children}</span> : null}
    </div>
  )
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div className="alert-box error" role="alert">
      {children}
    </div>
  )
}

interface FieldProps {
  label: string
  hint?: ReactNode
  error?: string
  className?: string
  children: (id: string, describedBy?: string) => ReactNode
}

/** Label + control + hint/error, with the accessibility wiring. */
export function Field({ label, hint, error, className, children }: FieldProps) {
  const id = useId()
  const describedBy = error || hint ? `${id}-desc` : undefined
  return (
    <label className={`field${className ? ` ${className}` : ''}`} htmlFor={id}>
      <span>{label}</span>
      {children(id, describedBy)}
      {error ? (
        <small id={describedBy} className="error">
          {error}
        </small>
      ) : hint ? (
        <small id={describedBy}>{hint}</small>
      ) : null}
    </label>
  )
}

export function Pagination({
  page,
  pageSize,
  count,
  onPage,
}: {
  page: number
  pageSize: number
  count: number
  onPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  const first = count ? (page - 1) * pageSize + 1 : 0
  const last = Math.min(page * pageSize, count)
  return (
    <div className="pagination">
      <span>
        {first}–{last} sur {count}
      </span>
      <div className="row">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Précédent
        </button>
        <span className="mono">
          {page} / {pages}
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Suivant
        </button>
      </div>
    </div>
  )
}
