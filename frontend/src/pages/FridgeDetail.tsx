import { lazy, Suspense, useState } from 'react'
import { Link, useParams } from 'react-router'
import useSWR from 'swr'
import { ExcursionMeter } from '../components/gauges'
import { ArrowLeftIcon, DownloadIcon } from '../components/icons'
import { PeriodPicker, periodQuery } from '../components/PeriodPicker'
import type { Period } from '../components/PeriodPicker'
import { useToast } from '../components/toast'
import {
  DeviceStatusBadge,
  Empty,
  ErrorBox,
  FridgeStatusBadge,
  IncidentStatusBadge,
  LevelChip,
  Spinner,
} from '../components/ui'
import { buildUrl, describeError, download } from '../lib/api'
import {
  formatDateTime,
  formatDuration,
  formatHumidity,
  formatNumber,
  formatShortDateTime,
  formatTemp,
  relativeTime,
} from '../lib/format'
import { INCIDENT_TYPE } from '../lib/labels'
import type { Fridge, Incident, Page, Series } from '../lib/types'

const SeriesCharts = lazy(() => import('../components/SeriesCharts'))

function seriesStats(series: Series | undefined, fridge: Fridge) {
  let min = Infinity
  let max = -Infinity
  let sum = 0
  let n = 0
  let out = 0
  for (const m of series?.results ?? []) {
    if (m.temperature == null) continue
    const t = m.temperature
    if (t < min) min = t
    if (t > max) max = t
    sum += t
    n += 1
    if (t < fridge.temp_min || t > fridge.temp_max) out += 1
  }
  return n ? { min, max, avg: sum / n, out, n } : null
}

export function FridgeDetailPage() {
  const { id } = useParams()
  const notify = useToast()
  const [period, setPeriod] = useState<Period>({ key: '24h' })
  const query = periodQuery(period)
  const customIncomplete = period.key === 'custom' && (!period.from || !period.to)

  const { data: fridge, error } = useSWR<Fridge>(`/api/fridges/${id}/`, { refreshInterval: 30_000 })
  const { data: series, isLoading: seriesLoading } = useSWR<Series>(
    customIncomplete ? null : buildUrl(`/api/fridges/${id}/measurements/`, query),
    { refreshInterval: period.key === 'custom' ? 0 : 60_000, keepPreviousData: true },
  )
  const { data: incidents } = useSWR<Page<Incident>>(`/api/incidents/?fridge=${id}&page_size=6`)

  if (error) return <ErrorBox>{describeError(error)}</ErrorBox>
  if (!fridge) return <Spinner />

  const stats = seriesStats(series, fridge)
  const incident = fridge.open_incident
  const last = fridge.last_measurement

  async function exportCsv() {
    try {
      await download(`/api/fridges/${id}/measurements/export/`, query, 'mesures.csv')
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  return (
    <>
      <Link to="/" className="back-link">
        <ArrowLeftIcon width={16} /> Tableau de bord
      </Link>
      <div className="page-head">
        <div>
          <p className="eyebrow">{fridge.location || 'Frigo'}</p>
          <h1>{fridge.name}</h1>
          <p>
            Plage autorisée{' '}
            <strong className="mono">
              {formatNumber(fridge.temp_min)} – {formatNumber(fridge.temp_max)} °C
            </strong>
            {fridge.hum_min != null && fridge.hum_max != null ? (
              <>
                {' · '}humidité{' '}
                <strong className="mono">
                  {fridge.hum_min} – {fridge.hum_max} %
                </strong>
              </>
            ) : null}
          </p>
        </div>
        <FridgeStatusBadge status={fridge.status} />
      </div>

      <div className="tiles">
        <div className="tile">
          <span className="eyebrow">Température</span>
          <span className="value">{last?.sensor_ok ? formatTemp(last.temperature) : '—'}</span>
        </div>
        <div className="tile">
          <span className="eyebrow">Humidité</span>
          <span className="value">{formatHumidity(last?.humidity)}</span>
        </div>
        <div className="tile">
          <span className="eyebrow">Dernière mesure</span>
          <span className="value" style={{ fontSize: 17 }}>
            {last ? relativeTime(last.received_at) : 'jamais'}
          </span>
        </div>
        <div className="tile">
          <span className="eyebrow">Nœud</span>
          <span className="value" style={{ fontSize: 15 }}>
            {fridge.device ? (
              <span className="row">
                {fridge.device.device_id} <DeviceStatusBadge status={fridge.device.status} />
              </span>
            ) : (
              'aucun'
            )}
          </span>
        </div>
      </div>

      {incident ? (
        <div className="card card-pad section tone-alert" style={{ borderColor: 'var(--alert)' }}>
          <div className="section-head">
            <h2>
              Incident en cours · {INCIDENT_TYPE[incident.type]}
            </h2>
            <div className="row">
              <IncidentStatusBadge status={incident.status} />
              <LevelChip level={incident.current_level} />
              <Link className="btn btn-primary btn-sm" to={`/incidents/${incident.id}`}>
                Ouvrir l’incident
              </Link>
            </div>
          </div>
          <ExcursionMeter minutes={incident.excursion_minutes} limitHours={fridge.max_excursion_hours} big />
          <p className="muted" style={{ margin: '10px 0 0', fontSize: 13 }}>
            Depuis le {formatDateTime(incident.started_at)}
            {incident.reagents_compromised ? ' · réactifs compromis' : ''}
          </p>
        </div>
      ) : null}

      <section className="section">
        <div className="section-head">
          <h2>Mesures</h2>
          <div className="row">
            <PeriodPicker value={period} onChange={setPeriod} />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={exportCsv}
              disabled={customIncomplete}
            >
              <DownloadIcon width={16} /> Export CSV
            </button>
          </div>
        </div>

        {stats ? (
          <div className="tiles" style={{ marginBottom: 14 }}>
            <div className="tile">
              <span className="eyebrow">Minimum</span>
              <span className="value">{formatTemp(stats.min)}</span>
            </div>
            <div className="tile">
              <span className="eyebrow">Moyenne</span>
              <span className="value">{formatTemp(stats.avg)}</span>
            </div>
            <div className="tile">
              <span className="eyebrow">Maximum</span>
              <span className="value">{formatTemp(stats.max)}</span>
            </div>
            <div className="tile">
              <span className="eyebrow">Hors plage</span>
              <span className="value" style={{ color: stats.out ? 'var(--alert)' : undefined }}>
                {stats.out} / {stats.n}
              </span>
            </div>
          </div>
        ) : null}

        <div className="stack">
          {series ? (
            <Suspense
              fallback={
                <div className="card chart-placeholder">
                  <div className="spinner" />
                </div>
              }
            >
              <SeriesCharts fridge={fridge} series={series} />
            </Suspense>
          ) : seriesLoading ? (
            <div className="card chart-placeholder">
              <div className="spinner" />
            </div>
          ) : (
            <div className="card chart-placeholder">Choisissez une période.</div>
          )}
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Derniers incidents</h2>
          <Link to={`/incidents?fridge=${fridge.id}`}>Tous les incidents de ce frigo</Link>
        </div>
        <div className="card table-wrap">
          {incidents?.results.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Début</th>
                  <th className="num">Hors plage</th>
                </tr>
              </thead>
              <tbody>
                {incidents.results.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">
                      <Link to={`/incidents/${row.id}`}>#{row.id}</Link>
                    </td>
                    <td>{row.type_label}</td>
                    <td>
                      <IncidentStatusBadge status={row.status} />
                    </td>
                    <td>{formatShortDateTime(row.started_at)}</td>
                    <td className="num">{formatDuration(row.excursion_minutes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty title="Aucun incident">Ce frigo n’a encore connu aucun incident.</Empty>
          )}
        </div>
      </section>
    </>
  )
}
