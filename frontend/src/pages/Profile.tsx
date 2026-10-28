import { useState } from 'react'
import type { FormEvent } from 'react'
import { useToast } from '../components/toast'
import { ErrorBox, Field } from '../components/ui'
import { api, describeError, fieldErrors } from '../lib/api'
import { useAuth } from '../lib/auth'
import { ROLE } from '../lib/labels'
import type { Profile } from '../lib/types'

function ProfileForm({ user }: { user: Profile }) {
  const { setUser } = useAuth()
  const notify = useToast()
  const [form, setForm] = useState({
    first_name: user.first_name,
    last_name: user.last_name,
    phone: user.phone,
    ntfy_topic: user.ntfy_topic,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  const update = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: e.target.value }))

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    try {
      const updated = await api<Profile>('/api/auth/me/', { method: 'PATCH', body: form })
      setUser(updated)
      notify('Profil enregistré.')
    } catch (err) {
      setErrors(fieldErrors(err))
      notify(describeError(err), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card card-pad" onSubmit={onSubmit}>
      <h2 style={{ fontSize: 18, marginBottom: 16 }}>Coordonnées et notifications</h2>
      <div className="form-grid">
        <Field label="Prénom" error={errors.first_name}>
          {(id) => <input id={id} className="input" value={form.first_name} onChange={update('first_name')} />}
        </Field>
        <Field label="Nom" error={errors.last_name}>
          {(id) => <input id={id} className="input" value={form.last_name} onChange={update('last_name')} />}
        </Field>
        <Field label="E-mail" hint="Modifiable par l’administrateur.">
          {(id, d) => <input id={id} className="input" value={user.email} readOnly disabled aria-describedby={d} />}
        </Field>
        <Field label="Téléphone" error={errors.phone}>
          {(id) => <input id={id} className="input" type="tel" value={form.phone} onChange={update('phone')} />}
        </Field>
        <Field
          className="full"
          label="Topic ntfy (notifications push)"
          error={errors.ntfy_topic}
          hint="Installez l’application ntfy, abonnez-vous à ce topic : les alertes arriveront avec un bouton « Je prends en charge ». Choisissez un nom difficile à deviner."
        >
          {(id, d) => (
            <input
              id={id}
              className="input mono"
              placeholder="coldchain-labo-7f3k9"
              value={form.ntfy_topic}
              onChange={update('ntfy_topic')}
              aria-describedby={d}
            />
          )}
        </Field>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </form>
  )
}

function PasswordForm() {
  const { logout } = useAuth()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    setError(null)
    try {
      await api('/api/auth/password/change/', {
        method: 'POST',
        body: { old_password: oldPassword, new_password: newPassword },
      })
      // Every session was revoked by the server: log in again with the new password.
      await logout()
    } catch (err) {
      const fields = fieldErrors(err)
      setErrors(fields)
      if (!Object.keys(fields).length) setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card card-pad" onSubmit={onSubmit}>
      <h2 style={{ fontSize: 18, marginBottom: 16 }}>Mot de passe</h2>
      {error ? <ErrorBox>{error}</ErrorBox> : null}
      <div className="form-grid">
        <Field label="Mot de passe actuel" error={errors.old_password}>
          {(id) => (
            <input
              id={id}
              className="input"
              type="password"
              autoComplete="current-password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
            />
          )}
        </Field>
        <Field label="Nouveau mot de passe" error={errors.new_password}>
          {(id) => (
            <input
              id={id}
              className="input"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="form-actions">
        <button className="btn btn-secondary" disabled={busy || !oldPassword || !newPassword}>
          {busy ? 'Modification…' : 'Changer le mot de passe'}
        </button>
      </div>
    </form>
  )
}

export function ProfilePage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">{ROLE[user.role]}</p>
          <h1>Mon profil</h1>
        </div>
      </div>
      <div className="stack" style={{ maxWidth: 760 }}>
        <ProfileForm user={user} />
        <PasswordForm />
      </div>
    </>
  )
}
