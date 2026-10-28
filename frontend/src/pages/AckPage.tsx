import { useState } from 'react'
import { useParams } from 'react-router'
import useSWR from 'swr'
import { ExcursionMeter } from '../components/gauges'
import { BrandMark, CheckCircleIcon } from '../components/icons'
import { ErrorBox, IncidentStatusBadge, LevelChip, Spinner } from '../components/ui'
import { api, ApiError, describeError } from '../lib/api'
import { formatDateTime } from '../lib/format'
import type { AckInfo } from '../lib/types'

/**
 * Mobile page opened from a notification. No login: the signed link identifies the
 * recipient. Opening it is recorded; only the button stops the escalation.
 */
export function AckPage() {
  const { token = '' } = useParams()
  const key = `/api/ack/${encodeURIComponent(token)}/`
  const { data, error, isLoading, mutate } = useSWR<AckInfo>(key, { revalidateOnFocus: false })
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function acknowledge() {
    setBusy(true)
    setActionError(null)
    try {
      const updated = await api<AckInfo>(key, { method: 'POST' })
      await mutate(updated, { revalidate: false })
      setDone(true)
    } catch (err) {
      setActionError(describeError(err))
      await mutate()
    } finally {
      setBusy(false)
    }
  }

  const incident = data?.incident

  return (
    <div className="ack-page">
      <div className="ack-bar">
        <span className="row" style={{ gap: 10, color: '#fff' }}>
          <BrandMark width={28} height={28} />
          <span className="brand-name">Cold Chain</span>
        </span>
      </div>

      <div className="card ack-card stack">
        {isLoading ? <Spinner /> : null}

        {error ? (
          <>
            <h1>Lien inutilisable</h1>
            <ErrorBox>
              {error instanceof ApiError && error.status === 400
                ? 'Ce lien est invalide ou a expiré. Ouvrez l’application pour prendre l’incident en charge.'
                : describeError(error)}
            </ErrorBox>
          </>
        ) : null}

        {incident ? (
          <>
            <div>
              <p className="eyebrow">Incident #{incident.id}</p>
              <h1>{incident.fridge_name}</h1>
              <div className="row" style={{ marginTop: 8 }}>
                <IncidentStatusBadge status={incident.status} />
                <span>{incident.type_label}</span>
                <LevelChip level={incident.current_level} />
              </div>
            </div>

            {incident.reagents_compromised ? (
              <ErrorBox>Plus de 10 h hors plage : les réactifs sont considérés comme compromis.</ErrorBox>
            ) : null}

            {incident.excursion_minutes > 0 ? (
              <ExcursionMeter
                minutes={incident.excursion_minutes}
                limitHours={incident.max_excursion_hours}
                big
              />
            ) : null}

            <dl className="facts">
              <dt>Début</dt>
              <dd>{formatDateTime(incident.started_at)}</dd>
              {incident.ended_at ? (
                <>
                  <dt>Fin</dt>
                  <dd>{formatDateTime(incident.ended_at)}</dd>
                </>
              ) : null}
              <dt>Destinataire</dt>
              <dd>{data.recipient}</dd>
            </dl>

            {actionError ? <ErrorBox>{actionError}</ErrorBox> : null}

            {done ? (
              <div className="ack-done">
                <CheckCircleIcon />
                <strong>Incident pris en charge.</strong>
                <span className="muted">L’escalade est suspendue. Pensez à commenter dans l’application.</span>
              </div>
            ) : data.can_ack ? (
              <button type="button" className="btn btn-danger btn-lg btn-block" disabled={busy} onClick={acknowledge}>
                {busy ? 'Envoi…' : 'Je prends en charge'}
              </button>
            ) : (
              <div className="alert-box info">
                {data.link_used
                  ? 'Vous avez déjà utilisé ce lien.'
                  : incident.status === 'open'
                    ? 'Ce lien ne permet plus la prise en charge.'
                    : `Incident ${incident.status_label.toLowerCase()} : aucune action nécessaire ici.`}
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}
