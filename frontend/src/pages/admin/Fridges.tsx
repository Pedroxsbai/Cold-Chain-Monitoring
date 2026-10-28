import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/toast'
import { Empty, ErrorBox, Field, FridgeStatusBadge, Spinner } from '../../components/ui'
import { api, describeError, fieldErrors } from '../../lib/api'
import { formatNumber, fullName } from '../../lib/format'
import { LEVEL } from '../../lib/labels'
import type { EscalationEntry, Fridge, Page, User } from '../../lib/types'

type Editing = { mode: 'create' } | { mode: 'edit'; fridge: Fridge } | { mode: 'thresholds'; fridge: Fridge } | { mode: 'chain'; fridge: Fridge } | null

const numberOrNull = (value: string) => (value.trim() === '' ? null : Number(value.replace(',', '.')))

function FridgeForm({ fridge, onDone }: { fridge?: Fridge; onDone: () => void }) {
  const notify = useToast()
  const [name, setName] = useState(fridge?.name ?? '')
  const [location, setLocation] = useState(fridge?.location ?? '')
  const [active, setActive] = useState(fridge?.is_active ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      const body = { name, location, is_active: active }
      await (fridge
        ? api(`/api/fridges/${fridge.id}/`, { method: 'PATCH', body })
        : api('/api/fridges/', { method: 'POST', body }))
      notify(fridge ? 'Frigo modifié.' : 'Frigo créé avec la plage 2–8 °C.')
      onDone()
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
        <Field label="Nom" error={errors.name} className="full">
          {(id) => <input id={id} className="input" required value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Emplacement" error={errors.location} className="full">
          {(id) => <input id={id} className="input" value={location} onChange={(e) => setLocation(e.target.value)} />}
        </Field>
        <label className="checkbox full">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Frigo surveillé (décocher pour le mettre hors service sans perdre son historique)
        </label>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy || !name.trim()}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </form>
  )
}

function ThresholdsForm({ fridge, onDone }: { fridge: Fridge; onDone: () => void }) {
  const notify = useToast()
  const [values, setValues] = useState({
    temp_min: String(fridge.temp_min),
    temp_max: String(fridge.temp_max),
    hum_min: fridge.hum_min == null ? '' : String(fridge.hum_min),
    hum_max: fridge.hum_max == null ? '' : String(fridge.hum_max),
    max_excursion_hours: String(fridge.max_excursion_hours),
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [key]: e.target.value }))

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    try {
      await api(`/api/fridges/${fridge.id}/thresholds/`, {
        method: 'PATCH',
        body: {
          temp_min: numberOrNull(values.temp_min),
          temp_max: numberOrNull(values.temp_max),
          hum_min: numberOrNull(values.hum_min),
          hum_max: numberOrNull(values.hum_max),
          max_excursion_hours: numberOrNull(values.max_excursion_hours),
        },
      })
      notify('Seuils enregistrés et journalisés.')
      onDone()
    } catch (err) {
      setErrors(fieldErrors(err))
      notify(describeError(err), 'error')
    } finally {
      setBusy(false)
    }
  }

  const input = (key: keyof typeof values, label: string, hint?: string) => (
    <Field label={label} error={errors[key]} hint={hint}>
      {(id, d) => (
        <input
          id={id}
          className="input mono"
          inputMode="decimal"
          aria-describedby={d}
          aria-invalid={Boolean(errors[key])}
          value={values[key]}
          onChange={set(key)}
        />
      )}
    </Field>
  )

  return (
    <form onSubmit={onSubmit}>
      <div className="alert-box info" style={{ marginBottom: 16 }}>
        Chaque modification est inscrite dans le journal d’événements.
      </div>
      <div className="form-grid">
        {input('temp_min', 'Température min (°C)')}
        {input('temp_max', 'Température max (°C)')}
        {input('hum_min', 'Humidité min (%)', 'Vide : humidité non surveillée.')}
        {input('hum_max', 'Humidité max (%)')}
        {input('max_excursion_hours', 'Durée max hors plage (h)', 'Au-delà, les réactifs sont compromis.')}
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Enregistrement…' : 'Enregistrer les seuils'}
        </button>
      </div>
    </form>
  )
}

function ChainEditor({ fridge }: { fridge: Fridge }) {
  const notify = useToast()
  const key = `/api/escalation/?fridge=${fridge.id}&page_size=100`
  const { data, mutate } = useSWR<Page<EscalationEntry>>(key)
  const { data: users } = useSWR<Page<User>>('/api/users/?is_active=true&page_size=500')
  const [user, setUser] = useState('')
  const [level, setLevel] = useState('1')
  const [busy, setBusy] = useState(false)

  async function add(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await api('/api/escalation/', {
        method: 'POST',
        body: { fridge: fridge.id, user: Number(user), level: Number(level) },
      })
      setUser('')
      await mutate()
    } catch (err) {
      notify(describeError(err), 'error')
    } finally {
      setBusy(false)
    }
  }

  async function remove(entry: EscalationEntry) {
    try {
      await api(`/api/escalation/${entry.id}/`, { method: 'DELETE' })
      await mutate()
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  if (!data) return <Spinner />

  return (
    <div className="stack">
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Les niveaux s’ajoutent : N1 est alerté d’abord, N2 rejoint à la 5ᵉ notification, N3 à la 9ᵉ. N1 reste alerté
        jusqu’au bout. Un même utilisateur peut être N1 ici et N2 ailleurs.
      </p>
      {[1, 2, 3].map((lvl) => {
        const entries = data.results.filter((e) => e.level === lvl)
        return (
          <div key={lvl}>
            <p className="eyebrow" style={{ margin: '0 0 6px' }}>
              {LEVEL[lvl]}
            </p>
            {entries.length ? (
              <div className="stack" style={{ gap: 6 }}>
                {entries.map((entry) => (
                  <div key={entry.id} className="row comment" style={{ justifyContent: 'space-between' }}>
                    <span>
                      <strong>{entry.user_name || entry.user_email}</strong>{' '}
                      <span className="muted">{entry.user_email}</span>
                    </span>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => remove(entry)}>
                      Retirer
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Personne.
              </p>
            )}
          </div>
        )
      })}
      <form className="toolbar" style={{ marginBottom: 0 }} onSubmit={add}>
        <Field label="Utilisateur">
          {(id) => (
            <select id={id} className="select" value={user} onChange={(e) => setUser(e.target.value)} required>
              <option value="">Choisir…</option>
              {users?.results.map((u) => (
                <option key={u.id} value={u.id}>
                  {fullName(u)} ({u.email})
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Niveau">
          {(id) => (
            <select id={id} className="select" value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="1">N1</option>
              <option value="2">N2</option>
              <option value="3">N3</option>
            </select>
          )}
        </Field>
        <button className="btn btn-primary" disabled={busy || !user}>
          Ajouter
        </button>
      </form>
    </div>
  )
}

export function AdminFridgesPage() {
  const notify = useToast()
  const { data, error, mutate } = useSWR<Page<Fridge>>('/api/fridges/?page_size=200')
  const [editing, setEditing] = useState<Editing>(null)

  const done = () => {
    setEditing(null)
    void mutate()
  }

  async function remove(fridge: Fridge) {
    if (!window.confirm(`Supprimer le frigo « ${fridge.name} » ?`)) return
    try {
      await api(`/api/fridges/${fridge.id}/`, { method: 'DELETE' })
      notify('Frigo supprimé.')
      await mutate()
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  const titles = {
    create: 'Nouveau frigo',
    edit: 'Modifier le frigo',
    thresholds: 'Seuils',
    chain: 'Chaîne d’escalade',
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Frigos</h1>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing({ mode: 'create' })}>
          Nouveau frigo
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
                <th>Nom</th>
                <th>Emplacement</th>
                <th className="num">Plage °C</th>
                <th className="num">Humidité %</th>
                <th className="num">Max h</th>
                <th>Nœud</th>
                <th>Statut</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.results.map((fridge) => (
                <tr key={fridge.id}>
                  <td>
                    <strong>{fridge.name}</strong>
                    {fridge.is_active ? null : <span className="muted"> · hors service</span>}
                  </td>
                  <td>{fridge.location || <span className="muted">—</span>}</td>
                  <td className="num">
                    {formatNumber(fridge.temp_min)} – {formatNumber(fridge.temp_max)}
                  </td>
                  <td className="num">
                    {fridge.hum_min != null && fridge.hum_max != null ? `${fridge.hum_min} – ${fridge.hum_max}` : '—'}
                  </td>
                  <td className="num">{fridge.max_excursion_hours}</td>
                  <td className="mono">{fridge.device?.device_id ?? <span className="muted">—</span>}</td>
                  <td>
                    <FridgeStatusBadge status={fridge.status} />
                  </td>
                  <td className="actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing({ mode: 'thresholds', fridge })}>
                      Seuils
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing({ mode: 'chain', fridge })}>
                      Chaîne
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing({ mode: 'edit', fridge })}>
                      Modifier
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => remove(fridge)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="Aucun frigo">Créez le premier frigo, puis rattachez-lui un nœud et une chaîne d’escalade.</Empty>
        )}
      </div>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing ? `${titles[editing.mode]}${'fridge' in editing ? ` · ${editing.fridge.name}` : ''}` : ''}
      >
        {editing?.mode === 'create' ? <FridgeForm onDone={done} /> : null}
        {editing?.mode === 'edit' ? <FridgeForm fridge={editing.fridge} onDone={done} /> : null}
        {editing?.mode === 'thresholds' ? <ThresholdsForm fridge={editing.fridge} onDone={done} /> : null}
        {editing?.mode === 'chain' ? <ChainEditor fridge={editing.fridge} /> : null}
      </Modal>
    </>
  )
}
