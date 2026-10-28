import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/toast'
import { Badge, Empty, ErrorBox, Field, Spinner } from '../../components/ui'
import { api, describeError, fieldErrors } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { formatShortDateTime, fullName } from '../../lib/format'
import { ROLE } from '../../lib/labels'
import type { Page, Role, User } from '../../lib/types'

function UserForm({ user, onDone }: { user?: User; onDone: () => void }) {
  const notify = useToast()
  const [form, setForm] = useState({
    email: user?.email ?? '',
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    phone: user?.phone ?? '',
    role: (user?.role ?? 'responsible') as Role,
    ntfy_topic: user?.ntfy_topic ?? '',
    is_active: user?.is_active ?? true,
    password: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    const { password, ...rest } = form
    const body = password ? form : rest
    try {
      await (user
        ? api(`/api/users/${user.id}/`, { method: 'PATCH', body })
        : api('/api/users/', { method: 'POST', body }))
      notify(user ? 'Utilisateur modifié.' : 'Utilisateur créé.')
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
        <Field label="E-mail (identifiant)" error={errors.email} className="full">
          {(id) => <input id={id} className="input" type="email" required value={form.email} onChange={set('email')} />}
        </Field>
        <Field label="Prénom" error={errors.first_name}>
          {(id) => <input id={id} className="input" value={form.first_name} onChange={set('first_name')} />}
        </Field>
        <Field label="Nom" error={errors.last_name}>
          {(id) => <input id={id} className="input" value={form.last_name} onChange={set('last_name')} />}
        </Field>
        <Field label="Téléphone" error={errors.phone}>
          {(id) => <input id={id} className="input" type="tel" value={form.phone} onChange={set('phone')} />}
        </Field>
        <Field label="Rôle" error={errors.role}>
          {(id) => (
            <select id={id} className="select" value={form.role} onChange={set('role')}>
              {Object.entries(ROLE).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Topic ntfy" error={errors.ntfy_topic} className="full">
          {(id) => <input id={id} className="input mono" value={form.ntfy_topic} onChange={set('ntfy_topic')} />}
        </Field>
        <Field
          label={user ? 'Nouveau mot de passe' : 'Mot de passe'}
          error={errors.password}
          className="full"
          hint={
            user
              ? 'Laisser vide pour ne pas le changer.'
              : 'Facultatif : sans mot de passe, l’utilisateur le choisit via « Mot de passe oublié ».'
          }
        >
          {(id, d) => (
            <input
              id={id}
              className="input"
              type="password"
              autoComplete="new-password"
              aria-describedby={d}
              value={form.password}
              onChange={set('password')}
            />
          )}
        </Field>
        <label className="checkbox full">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          />
          Compte actif (un compte inactif ne peut plus se connecter ni être notifié)
        </label>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy || !form.email}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </form>
  )
}

export function AdminUsersPage() {
  const notify = useToast()
  const { user: me } = useAuth()
  const { data, error, mutate } = useSWR<Page<User>>('/api/users/?page_size=500')
  const [editing, setEditing] = useState<User | 'new' | null>(null)

  async function remove(user: User) {
    if (!window.confirm(`Supprimer le compte de ${fullName(user)} ? Préférez la désactivation pour garder la traçabilité.`)) return
    try {
      await api(`/api/users/${user.id}/`, { method: 'DELETE' })
      notify('Utilisateur supprimé.')
      await mutate()
    } catch (err) {
      notify(describeError(err), 'error')
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Utilisateurs</h1>
          <p>Le rôle est global ; le niveau N1/N2/N3 se règle frigo par frigo, dans sa chaîne d’escalade.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
          Nouvel utilisateur
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
                <th>E-mail</th>
                <th>Téléphone</th>
                <th>Rôle</th>
                <th>Push</th>
                <th>Dernière connexion</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.results.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{fullName(user)}</strong>
                    {user.is_active ? null : (
                      <>
                        {' '}
                        <Badge tone="off">inactif</Badge>
                      </>
                    )}
                  </td>
                  <td>{user.email}</td>
                  <td className="mono">{user.phone || <span className="muted">—</span>}</td>
                  <td>{ROLE[user.role]}</td>
                  <td>{user.ntfy_topic ? <Badge tone="ok">ntfy</Badge> : <span className="muted">e-mail seul</span>}</td>
                  <td className="mono muted">{formatShortDateTime(user.last_login)}</td>
                  <td className="actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(user)}>
                      Modifier
                    </button>
                    {user.id !== me?.id ? (
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => remove(user)}>
                        Supprimer
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="Aucun utilisateur" />
        )}
      </div>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Nouvel utilisateur' : editing ? `Modifier ${fullName(editing)}` : ''}
      >
        {editing ? (
          <UserForm
            key={editing === 'new' ? 'new' : editing.id}
            user={editing === 'new' ? undefined : editing}
            onDone={() => {
              setEditing(null)
              void mutate()
            }}
          />
        ) : null}
      </Modal>
    </>
  )
}
