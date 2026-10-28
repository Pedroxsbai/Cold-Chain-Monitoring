import { useSearchParams } from 'react-router'
import useSWR from 'swr'
import { DownloadIcon } from '../components/icons'
import { useToast } from '../components/toast'
import { Empty, ErrorBox, Field, Pagination, Spinner } from '../components/ui'
import { buildUrl, describeError, download } from '../lib/api'
import { formatDateTime, formatHumidity, formatTemp } from '../lib/format'
import type { Fridge, Measurement, Page } from '../lib/types'

const PAGE_SIZE = 50

export function HistoryPage() {
  const notify = useToast()
  // Filters live in the URL so a filtered view can be shared or reloaded.
  const [params, setParams] = useSearchParams()
  const fridge = params.get('fridge') ?? ''
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const page = Number(params.get('page') ?? 1)

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  const { data: fridges } = useSWR<Page<Fridge>>('/api/fridges/?page_size=200')
  const { data, error, isLoading } = useSWR<Page<Measurement>>(
    buildUrl('/api/measurements/', { fridge, from, to, page, page_size: PAGE_SIZE }),
    { keepPreviousData: true },
  )
  const thresholds = new Map(fridges?.results.map((f) => [f.id, f]))

  async function exportCsv() {
    try {
      await download(`/api/fridges/${fridge}/measurements/export/`, { from, to }, 'mesures.csv')
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Toutes les mesures reçues</p>
          <h1>Historique</h1>
        </div>
      </div>

      <div className="toolbar">
        <Field label="Frigo">
          {(id) => (
            <select id={id} className="select" value={fridge} onChange={(e) => setFilter('fridge', e.target.value)}>
              <option value="">Tous</option>
              {fridges?.results.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Du">
          {(id) => (
            <input id={id} type="date" className="input" value={from} max={to || undefined} onChange={(e) => setFilter('from', e.target.value)} />
          )}
        </Field>
        <Field label="Au">
          {(id) => (
            <input id={id} type="date" className="input" value={to} min={from || undefined} onChange={(e) => setFilter('to', e.target.value)} />
          )}
        </Field>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={exportCsv}
          disabled={!fridge}
          title={fridge ? undefined : 'Choisissez un frigo pour exporter'}
        >
          <DownloadIcon width={16} /> Export CSV
        </button>
      </div>
      {!fridge ? (
        <p className="muted" style={{ marginTop: -6, fontSize: 13 }}>
          L’export CSV se fait frigo par frigo, sur la période choisie (24 h par défaut).
        </p>
      ) : null}

      {error ? <ErrorBox>{describeError(error)}</ErrorBox> : null}

      <div className="card">
        {isLoading && !data ? <Spinner /> : null}
        {data ? (
          data.results.length ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Frigo</th>
                      <th className="num">Température</th>
                      <th className="num">Humidité</th>
                      <th>Capteur</th>
                      <th>Nœud</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((m) => {
                      const f = thresholds.get(m.fridge)
                      const out =
                        f && m.temperature != null && (m.temperature < f.temp_min || m.temperature > f.temp_max)
                      return (
                        <tr key={m.id}>
                          <td className="mono">{formatDateTime(m.received_at)}</td>
                          <td>{m.fridge_name}</td>
                          <td className={`num${out ? ' out' : ''}`}>{formatTemp(m.temperature)}</td>
                          <td className="num">{formatHumidity(m.humidity)}</td>
                          <td>{m.sensor_ok ? 'OK' : <span className="out">Défaut</span>}</td>
                          <td className="mono muted">{m.device_id ?? '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                count={data.count}
                onPage={(p) => setFilter('page', String(p))}
              />
            </>
          ) : (
            <Empty title="Aucune mesure">Aucune mesure ne correspond à ces filtres.</Empty>
          )
        ) : null}
      </div>
    </>
  )
}
