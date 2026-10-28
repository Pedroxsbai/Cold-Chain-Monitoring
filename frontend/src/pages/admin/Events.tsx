import { useSearchParams } from 'react-router'
import useSWR from 'swr'
import { Empty, ErrorBox, Field, Pagination, Spinner } from '../../components/ui'
import { buildUrl, describeError } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { EVENT_TYPES } from '../../lib/labels'
import type { EventLog, Page } from '../../lib/types'

const PAGE_SIZE = 50

function details(event: EventLog) {
  const entries = Object.entries(event.details)
  if (!entries.length) return null
  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(' · ')
}

export function AdminEventsPage() {
  const [params, setParams] = useSearchParams()
  const type = params.get('type') ?? ''
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

  const { data, error, isLoading } = useSWR<Page<EventLog>>(
    buildUrl('/api/events/', { type, from, to, page, page_size: PAGE_SIZE }),
    { keepPreviousData: true },
  )

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Administration · lecture seule</p>
          <h1>Journal d’événements</h1>
          <p>Chaque mesure hors plage, alerte, prise en charge, modification de seuil et connexion.</p>
        </div>
      </div>

      <div className="toolbar">
        <Field label="Type d’événement">
          {(id) => (
            <select id={id} className="select" value={type} onChange={(e) => setFilter('type', e.target.value)}>
              <option value="">Tous</option>
              {EVENT_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Du">
          {(id) => <input id={id} type="date" className="input" value={from} onChange={(e) => setFilter('from', e.target.value)} />}
        </Field>
        <Field label="Au">
          {(id) => <input id={id} type="date" className="input" value={to} onChange={(e) => setFilter('to', e.target.value)} />}
        </Field>
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
                      <th>Horodatage</th>
                      <th>Événement</th>
                      <th>Acteur</th>
                      <th>Objet</th>
                      <th>Détails</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((event) => (
                      <tr key={event.id}>
                        <td className="mono" style={{ whiteSpace: 'nowrap' }}>
                          {formatDateTime(event.timestamp)}
                        </td>
                        <td>
                          <strong>{event.type_label}</strong>
                        </td>
                        <td>{event.actor_label || '—'}</td>
                        <td>{event.object_repr || '—'}</td>
                        <td className="details-json">{details(event) ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPage={(p) => setFilter('page', String(p))} />
            </>
          ) : (
            <Empty title="Aucun événement">Aucun événement ne correspond à ces filtres.</Empty>
          )
        ) : null}
      </div>
    </>
  )
}
