import type { CSSProperties } from 'react'
import { Link } from 'react-router'
import useSWR from 'swr'
import { ExcursionMeter, RangeGauge } from '../components/gauges'
import { Empty, ErrorBox, FRIDGE_TONE, FridgeStatusBadge, Spinner } from '../components/ui'
import { describeError } from '../lib/api'
import { formatHumidity, formatNumber, formatTime, relativeTime } from '../lib/format'
import { INCIDENT_TYPE } from '../lib/labels'
import type { Fridge, FridgeStatus, Page } from '../lib/types'

const ORDER: Record<FridgeStatus, number> = { alert: 0, offline: 1, normal: 2 }

function FridgeCard({ fridge, index }: { fridge: Fridge; index: number }) {
  const tone = FRIDGE_TONE[fridge.status]
  const last = fridge.last_measurement
  const incident = fridge.open_incident
  const temp = last?.sensor_ok ? last.temperature : null
  const outOfRange = temp != null && (temp < fridge.temp_min || temp > fridge.temp_max)

  return (
    <Link
      to={`/frigos/${fridge.id}`}
      className={`card fridge-card reveal tone-${tone}`}
      style={
        {
          '--i': index,
          '--tone-text': outOfRange ? 'var(--alert)' : undefined,
        } as CSSProperties
      }
    >
      <header>
        <div>
          <h3>{fridge.name}</h3>
          <div className="location">{fridge.location || 'Emplacement non précisé'}</div>
        </div>
        <FridgeStatusBadge status={fridge.status} />
      </header>

      <div className="reading">
        <span className="temp">
          {temp == null ? '—' : formatNumber(temp)}
          <small>°C</small>
        </span>
        <span className="hum">{formatHumidity(last?.humidity)} HR</span>
      </div>

      <RangeGauge value={temp} min={fridge.temp_min} max={fridge.temp_max} tone={tone} />

      {incident ? (
        <div className="incident-strip">
          <div className="row">
            <span>{INCIDENT_TYPE[incident.type]}</span>
            <span>
              {incident.status === 'acknowledged' ? 'Pris en charge' : 'En attente'} · N
              {incident.current_level}
            </span>
          </div>
          {incident.excursion_minutes > 0 ? (
            <ExcursionMeter minutes={incident.excursion_minutes} limitHours={fridge.max_excursion_hours} />
          ) : null}
        </div>
      ) : null}

      <footer className="card-foot">
        <span>
          {last ? (
            <>
              Mesure {relativeTime(last.received_at)} · {formatTime(last.received_at)}
            </>
          ) : (
            'Aucune mesure reçue'
          )}
        </span>
        <span className="mono">{fridge.device?.device_id ?? 'sans nœud'}</span>
      </footer>
    </Link>
  )
}

export function DashboardPage() {
  const { data, error, isLoading } = useSWR<Page<Fridge>>('/api/fridges/?is_active=true&page_size=200', {
    refreshInterval: 30_000,
  })

  const fridges = (data?.results ?? []).toSorted(
    (a, b) => ORDER[a.status] - ORDER[b.status] || a.name.localeCompare(b.name, 'fr'),
  )
  const counts = { normal: 0, alert: 0, offline: 0 }
  for (const fridge of fridges) counts[fridge.status] += 1

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Surveillance en continu</p>
          <h1>Tableau de bord</h1>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          Actualisation automatique toutes les 30 s
        </span>
      </div>

      {error ? <ErrorBox>{describeError(error)}</ErrorBox> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="summary">
            <div>
              <span className="eyebrow">Frigos suivis</span>
              <span className="value">{fridges.length}</span>
            </div>
            <div style={{ '--tone': 'var(--ok)' } as CSSProperties}>
              <span className="eyebrow">Normaux</span>
              <span className="value">{counts.normal}</span>
            </div>
            <div style={{ '--tone': counts.alert ? 'var(--alert)' : undefined } as CSSProperties}>
              <span className="eyebrow">En alerte</span>
              <span className="value">{counts.alert}</span>
            </div>
            <div style={{ '--tone': counts.offline ? 'var(--off)' : undefined } as CSSProperties}>
              <span className="eyebrow">Hors ligne</span>
              <span className="value">{counts.offline}</span>
            </div>
          </div>

          {fridges.length ? (
            <div className="fridge-grid">
              {fridges.map((fridge, index) => (
                <FridgeCard key={fridge.id} fridge={fridge} index={index} />
              ))}
            </div>
          ) : (
            <div className="card">
              <Empty title="Aucun frigo à afficher">
                Vous n’êtes rattaché à aucune chaîne d’escalade. Contactez l’administrateur.
              </Empty>
            </div>
          )}
        </>
      ) : null}
    </>
  )
}
