import { useNavigate, useSearchParams } from 'react-router'
import useSWR from 'swr'
import { Empty, ErrorBox, Field, IncidentStatusBadge, LevelChip, Pagination, Spinner } from '../components/ui'
import { buildUrl, describeError } from '../lib/api'
import { formatDuration, formatShortDateTime } from '../lib/format'
import { INCIDENT_STATUS, INCIDENT_TYPE } from '../lib/labels'
import type { Fridge, Incident, Page } from '../lib/types'

const PAGE_SIZE = 25

export function IncidentsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const scope = params.get('scope') ?? 'active'
  const fridge = params.get('fridge') ?? ''
  const type = params.get('type') ?? ''
  const status = params.get('status') ?? ''
  const page = Number(params.get('page') ?? 1)

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  const { data: fridges } = useSWR<Page<Fridge>>('/api/fridges/?page_size=200')
  const { data, error, isLoading } = useSWR<Page<Incident>>(
    buildUrl('/api/incidents/', {
      active: scope === 'active' ? 'true' : undefined,
      fridge,
      type,
      status: scope === 'all' ? status : undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    { refreshInterval: 30_000, keepPreviousData: true },
  )

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Ouverture, prise en charge, clôture</p>
          <h1>Incidents</h1>
        </div>
        <div className="segmented" role="group" aria-label="Incidents affichés">
          <button type="button" aria-pressed={scope === 'active'} onClick={() => setFilter('scope', '')}>
            En cours
          </button>
          <button type="button" aria-pressed={scope === 'all'} onClick={() => setFilter('scope', 'all')}>
            Tous
          </button>
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
        <Field label="Type">
          {(id) => (
            <select id={id} className="select" value={type} onChange={(e) => setFilter('type', e.target.value)}>
              <option value="">Tous</option>
              {Object.entries(INCIDENT_TYPE).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
        </Field>
        {scope === 'all' ? (
          <Field label="Statut">
            {(id) => (
              <select id={id} className="select" value={status} onChange={(e) => setFilter('status', e.target.value)}>
                <option value="">Tous</option>
                {Object.entries(INCIDENT_STATUS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        ) : null}
      </div>

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
                      <th>#</th>
                      <th>Frigo</th>
                      <th>Type</th>
                      <th>Statut</th>
                      <th>Niveau</th>
                      <th>Début</th>
                      <th className="num">Hors plage</th>
                      <th>Pris en charge par</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((incident) => (
                      <tr
                        key={incident.id}
                        className="clickable"
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                      >
                        <td className="mono">#{incident.id}</td>
                        <td>
                          <strong>{incident.fridge_name}</strong>
                        </td>
                        <td>{incident.type_label}</td>
                        <td>
                          <IncidentStatusBadge status={incident.status} />
                        </td>
                        <td>
                          <LevelChip level={incident.current_level} />
                        </td>
                        <td>{formatShortDateTime(incident.started_at)}</td>
                        <td className={`num${incident.reagents_compromised ? ' out' : ''}`}>
                          {formatDuration(incident.excursion_minutes)}
                        </td>
                        <td>{incident.acked_by_name ?? <span className="muted">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPage={(p) => setFilter('page', String(p))} />
            </>
          ) : (
            <Empty title={scope === 'active' ? 'Aucun incident en cours' : 'Aucun incident'}>
              {scope === 'active' ? 'Tous les frigos sont dans leur plage.' : 'Aucun incident ne correspond à ces filtres.'}
            </Empty>
          )
        ) : null}
      </div>
    </>
  )
}
