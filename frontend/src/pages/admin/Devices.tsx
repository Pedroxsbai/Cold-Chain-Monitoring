import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { CopyIcon } from '../../components/icons'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/toast'
import { DeviceStatusBadge, Empty, ErrorBox, Field, Spinner } from '../../components/ui'
import { api, describeError, fieldErrors } from '../../lib/api'
import { formatShortDateTime, relativeTime } from '../../lib/format'
import type { Device, Fridge, Page } from '../../lib/types'

type Editing = { mode: 'create' } | { mode: 'edit'; device: Device } | null

type Revealed = { deviceId: string; apiKey: string }

function DeviceForm({
  device,
  fridges,
  onSaved,
}: {
  device?: Device
  fridges: Fridge[]
  onSaved: (revealed?: Revealed) => void
}) {
  const notify = useToast()
  const [deviceId, setDeviceId] = useState(device?.device_id ?? '')
  const [fridge, setFridge] = useState(device?.fridge ? String(device.fridge) : '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  // A fridge has at most one node: offer free fridges plus the current one.
  const available = fridges.filter((f) => !f.device || f.device.id === device?.id)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    const body = { device_id: deviceId, fridge: fridge ? Number(fridge) : null }
    try {
      if (device) {
        await api(`/api/devices/${device.id}/`, { method: 'PATCH', body })
        notify('Nœud modifié.')
        onSaved()
      } else {
        const created = await api<Device & { api_key: string }>('/api/devices/', { method: 'POST', body })
        onSaved({ deviceId: created.device_id, apiKey: created.api_key })
      }
    } catch (err) {
      setErrors(fieldErrors(err))
      notify(describeError(err), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="form-grid">
        <Field label="Identifiant du nœud" error={errors.device_id} hint="Celui du firmware, ex. FRIGO-LAB-02." className="full">
          {(id, d) => (
            <input
              id={id}
              className="input mono"
              required
              aria-describedby={d}
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value.toUpperCase())}
            />
          )}
        </Field>
        <Field label="Frigo" error={errors.fridge} className="full">
          {(id) => (
            <select id={id} className="select" value={fridge} onChange={(e) => setFridge(e.target.value)}>
              <option value="">Non rattaché</option>
              {available.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy || !deviceId.trim()}>
          {busy ? 'Enregistrement…' : device ? 'Enregistrer' : 'Créer et générer la clé'}
        </button>
      </div>
    </form>
  )
}

function KeyReveal({ deviceId, apiKey }: { deviceId: string; apiKey: string }) {
  const notify = useToast()
  const snippet = `const char* DEVICE_ID  = "${deviceId}";\nconst char* DEVICE_KEY = "${apiKey}";`
  const copy = (text: string) =>
    navigator.clipboard.writeText(text).then(
      () => notify('Copié dans le presse-papiers.'),
      () => notify('Copie impossible : sélectionnez le texte.', 'error'),
    )
  return (
    <div className="stack">
      <div className="alert-box error">
        Cette clé n’est affichée qu’une seule fois. Copiez-la maintenant dans le firmware du nœud.
      </div>
      <div className="key-box">
        <code>{apiKey}</code>
        <button type="button" className="btn btn-ghost btn-sm" style={{ color: 'inherit' }} onClick={() => copy(apiKey)} aria-label="Copier la clé">
          <CopyIcon width={16} />
        </button>
      </div>
      <div>
        <p className="eyebrow" style={{ margin: '0 0 6px' }}>
          À placer dans firmware/secrets.h
        </p>
        <pre className="code-block">{snippet}</pre>
      </div>
      <button type="button" className="btn btn-secondary" onClick={() => copy(snippet)}>
        Copier le bloc
      </button>
    </div>
  )
}

export function AdminDevicesPage() {
  const notify = useToast()
  const { data, error, mutate } = useSWR<Page<Device>>('/api/devices/?page_size=200', { refreshInterval: 30_000 })
  const { data: fridges, mutate: mutateFridges } = useSWR<Page<Fridge>>('/api/fridges/?page_size=200')
  const [editing, setEditing] = useState<Editing>(null)
  const [revealed, setRevealed] = useState<Revealed | null>(null)

  function refresh() {
    void mutate()
    void mutateFridges()
  }

  async function rotate(device: Device) {
    if (!window.confirm(`Générer une nouvelle clé pour ${device.device_id} ? L’ancienne cessera immédiatement de fonctionner.`)) return
    try {
      const { api_key } = await api<{ api_key: string }>(`/api/devices/${device.id}/rotate-key/`, { method: 'POST' })
      setRevealed({ deviceId: device.device_id, apiKey: api_key })
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  async function remove(device: Device) {
    if (!window.confirm(`Supprimer le nœud ${device.device_id} ? Ses mesures sont conservées.`)) return
    try {
      await api(`/api/devices/${device.id}/`, { method: 'DELETE' })
      notify('Nœud supprimé.')
      refresh()
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Nœuds IoT</h1>
          <p>ESP8266 + capteur DHT, une mesure toutes les 20 min, authentifiés par une clé propre.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing({ mode: 'create' })}>
          Nouveau nœud
        </button>
      </div>

      {error ? <ErrorBox>{describeError(error)}</ErrorBox> : null}

      <div className="card table-wrap">
        {!data ? (
          <Spinner />
        ) : data.results.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Identifiant</th>
                <th>Frigo</th>
                <th>Statut</th>
                <th>Dernière mesure</th>
                <th>Firmware</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.results.map((device) => (
                <tr key={device.id}>
                  <td className="mono">
                    <strong>{device.device_id}</strong>
                  </td>
                  <td>{device.fridge_name ?? <span className="muted">non rattaché</span>}</td>
                  <td>
                    <DeviceStatusBadge status={device.status} />
                  </td>
                  <td title={formatShortDateTime(device.last_seen)}>{relativeTime(device.last_seen)}</td>
                  <td className="mono muted">{device.firmware || '—'}</td>
                  <td className="actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing({ mode: 'edit', device })}>
                      Modifier
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => rotate(device)}>
                      Nouvelle clé
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => remove(device)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="Aucun nœud">Déclarez un nœud pour obtenir sa clé API.</Empty>
        )}
      </div>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.mode === 'edit' ? `Modifier ${editing.device.device_id}` : 'Nouveau nœud'}
      >
        {editing ? (
          <DeviceForm
            device={editing.mode === 'edit' ? editing.device : undefined}
            fridges={fridges?.results ?? []}
            onSaved={(created) => {
              setEditing(null)
              refresh()
              if (created) setRevealed(created)
            }}
          />
        ) : null}
      </Modal>

      <Modal open={revealed !== null} onClose={() => setRevealed(null)} title="Clé API du nœud">
        {revealed ? <KeyReveal deviceId={revealed.deviceId} apiKey={revealed.apiKey} /> : null}
      </Modal>
    </>
  )
}
