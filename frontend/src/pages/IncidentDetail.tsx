import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import useSWR from 'swr'
import { ExcursionMeter } from '../components/gauges'
import { ArrowLeftIcon } from '../components/icons'
import { useToast } from '../components/toast'
import { Badge, Empty, ErrorBox, Field, IncidentStatusBadge, LevelChip, Spinner } from '../components/ui'
import { api, describeError } from '../lib/api'
import { formatDateTime, formatShortDateTime } from '../lib/format'
import { CHANNEL } from '../lib/labels'
import type { Fridge, IncidentDetail } from '../lib/types'

function Timeline({ incident }: { incident: IncidentDetail }) {
  const steps: { at: string; label: string; tone: string }[] = [
    { at: incident.started_at, label: `Ouverture · ${incident.type_label.toLowerCase()}`, tone: 'var(--alert)' },
  ]
  if (incident.acked_at) {
    steps.push({ at: incident.acked_at, label: `Pris en charge par ${incident.acked_by_name}`, tone: 'var(--warn)' })
  }
  if (incident.ended_at) {
    steps.push({ at: incident.ended_at, label: 'Retour dans la plage', tone: 'var(--ice)' })
  }
  if (incident.closed_at) {
    steps.push({ at: incident.closed_at, label: `Clôturé par ${incident.closed_by_name}`, tone: 'var(--ok)' })
  }
  return (
    <ol className="timeline">
      {steps.map((step) => (
        <li key={step.label} style={{ '--tone': step.tone } as CSSProperties}>
          <time dateTime={step.at}>{formatDateTime(step.at)}</time>
          {step.label}
        </li>
      ))}
    </ol>
  )
}

export function IncidentDetailPage() {
  const { id } = useParams()
  const notify = useToast()
  const key = `/api/incidents/${id}/`
  const { data: incident, error, mutate } = useSWR<IncidentDetail>(key, { refreshInterval: 30_000 })
  const { data: fridge } = useSWR<Fridge>(incident ? `/api/fridges/${incident.fridge}/` : null)
  const [comment, setComment] = useState('')
  const [closing, setClosing] = useState('')
  const [busy, setBusy] = useState<'ack' | 'comment' | 'close' | null>(null)

  if (error) return <ErrorBox>{describeError(error)}</ErrorBox>
  if (!incident) return <Spinner />

  async function run(action: 'ack' | 'comment' | 'close', request: () => Promise<unknown>, message: string) {
    setBusy(action)
    try {
      await request()
      await mutate()
      notify(message)
      return true
    } catch (err) {
      notify(describeError(err), 'error')
      await mutate()
      return false
    } finally {
      setBusy(null)
    }
  }

  const acknowledge = () =>
    run('ack', () => api(`${key}ack/`, { method: 'POST' }), 'Incident pris en charge. L’escalade est suspendue.')

  async function addComment(event: FormEvent) {
    event.preventDefault()
    const ok = await run(
      'comment',
      () => api(`${key}comments/`, { method: 'POST', body: { text: comment } }),
      'Commentaire ajouté.',
    )
    if (ok) setComment('')
  }

  async function close(event: FormEvent) {
    event.preventDefault()
    await run('close', () => api(`${key}close/`, { method: 'POST', body: { comment: closing } }), 'Incident clôturé.')
  }

  const limit = fridge?.max_excursion_hours ?? 10

  return (
    <>
      <Link to="/incidents" className="back-link">
        <ArrowLeftIcon width={16} /> Incidents
      </Link>
      <div className="page-head">
        <div>
          <p className="eyebrow">Incident #{incident.id}</p>
          <h1>
            {incident.fridge_name} · {incident.type_label}
          </h1>
          <div className="row" style={{ marginTop: 10 }}>
            <IncidentStatusBadge status={incident.status} />
            <LevelChip level={incident.current_level} />
            {incident.reagents_compromised ? <Badge tone="alert">Réactifs compromis</Badge> : null}
            {incident.out_of_range_now ? <Badge tone="warn">Hors plage en ce moment</Badge> : null}
          </div>
        </div>
        {incident.can_ack ? (
          <button type="button" className="btn btn-danger btn-lg" disabled={busy !== null} onClick={acknowledge}>
            {busy === 'ack' ? 'Envoi…' : 'Je prends en charge'}
          </button>
        ) : null}
      </div>

      <div className="split">
        <div className="stack">
          <div className="card card-pad">
            <div className="section-head">
              <h2>Compteur d’excursion</h2>
              <span className="muted" style={{ fontSize: 13 }}>
                Seuil : {limit} h cumulées hors plage
              </span>
            </div>
            <ExcursionMeter minutes={incident.excursion_minutes} limitHours={limit} big />
            {incident.severity_hours_reached ? (
              <p className="muted" style={{ margin: '10px 0 0', fontSize: 13 }}>
                Seuil de gravité atteint : {incident.severity_hours_reached} h — tous les niveaux ont été alertés.
              </p>
            ) : null}
          </div>

          <div className="card card-pad">
            <h2 style={{ fontSize: 18, marginBottom: 14 }}>Commentaires</h2>
            <div className="stack">
              {incident.comments.length ? (
                incident.comments.map((c) => (
                  <article key={c.id} className="comment">
                    <header>
                      <strong>{c.author_name ?? 'Utilisateur supprimé'}</strong>
                      <time className="mono muted">{formatShortDateTime(c.created_at)}</time>
                    </header>
                    <p>{c.text}</p>
                  </article>
                ))
              ) : (
                <p className="muted" style={{ margin: 0 }}>
                  Aucun commentaire pour l’instant.
                </p>
              )}
              <form className="stack" onSubmit={addComment}>
                <Field label="Ajouter un commentaire">
                  {(fieldId) => (
                    <textarea
                      id={fieldId}
                      className="textarea"
                      placeholder="Ex. : porte mal fermée, refermée à 14 h 20."
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                    />
                  )}
                </Field>
                <div className="row" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn btn-secondary" disabled={!comment.trim() || busy !== null}>
                    {busy === 'comment' ? 'Envoi…' : 'Commenter'}
                  </button>
                </div>
              </form>
            </div>
          </div>

          <div className="card">
            <div className="card-pad" style={{ paddingBottom: 8 }}>
              <h2 style={{ fontSize: 18 }}>Notifications envoyées</h2>
            </div>
            {incident.notifications.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Destinataire</th>
                      <th>Canal</th>
                      <th>Niveau</th>
                      <th>Statut</th>
                      <th>Lue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incident.notifications.map((n) => (
                      <tr key={n.id}>
                        <td className="mono">{formatShortDateTime(n.sent_at)}</td>
                        <td>
                          {n.user_name ?? '—'}
                          {n.kind === 'resolved' ? <span className="muted"> · fin</span> : null}
                        </td>
                        <td>{CHANNEL[n.channel]}</td>
                        <td>
                          <LevelChip level={n.level} />
                        </td>
                        <td title={n.error || undefined}>
                          {n.status === 'sent' ? (
                            <Badge tone="ok">Envoyée</Badge>
                          ) : n.status === 'failed' ? (
                            <Badge tone="alert">Échec</Badge>
                          ) : (
                            <Badge tone="off">En attente</Badge>
                          )}
                        </td>
                        <td className="mono muted">{n.read_at ? formatShortDateTime(n.read_at) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Aucune notification">Le moteur d’alertes enverra la première sous une minute.</Empty>
            )}
          </div>
        </div>

        <div className="stack">
          <div className="card card-pad">
            <h2 style={{ fontSize: 18, marginBottom: 14 }}>Chronologie</h2>
            <Timeline incident={incident} />
          </div>

          <div className="card card-pad">
            <dl className="facts">
              <dt>Notifications</dt>
              <dd className="mono">{incident.notification_count}</dd>
              <dt>Dernière</dt>
              <dd>{formatShortDateTime(incident.last_notified_at)}</dd>
              <dt>Frigo</dt>
              <dd>
                <Link to={`/frigos/${incident.fridge}`}>{incident.fridge_name}</Link>
              </dd>
            </dl>
          </div>

          {incident.status === 'closed' ? (
            <div className="card card-pad">
              <h2 style={{ fontSize: 18, marginBottom: 8 }}>Clôture</h2>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{incident.closing_comment}</p>
            </div>
          ) : incident.can_close ? (
            <form className="card card-pad stack" onSubmit={close}>
              <h2 style={{ fontSize: 18 }}>Clôturer l’incident</h2>
              <Field label="Commentaire de clôture" hint="Obligatoire : cause, actions menées, état des réactifs.">
                {(fieldId, describedBy) => (
                  <textarea
                    id={fieldId}
                    className="textarea"
                    aria-describedby={describedBy}
                    value={closing}
                    onChange={(e) => setClosing(e.target.value)}
                  />
                )}
              </Field>
              <button className="btn btn-primary" disabled={!closing.trim() || busy !== null}>
                {busy === 'close' ? 'Clôture…' : 'Clôturer'}
              </button>
            </form>
          ) : incident.status === 'ended' ? (
            <div className="alert-box info">
              Incident terminé. La clôture avec commentaire est faite par le N2 ou l’administrateur.
            </div>
          ) : null}
        </div>
      </div>
    </>
  )
}
