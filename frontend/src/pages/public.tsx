import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'
import { BrandMark } from '../components/icons'
import { ErrorBox, Field } from '../components/ui'
import { api, ApiError, describeError, fieldErrors } from '../lib/api'
import { useAuth } from '../lib/auth'

function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="public">
      <section className="public-art" aria-hidden="true">
        <div className="row" style={{ gap: 12 }}>
          <BrandMark width={40} height={40} />
          <span className="brand-name" style={{ color: '#fff' }}>
            Cold Chain
            <small>Monitoring</small>
          </span>
        </div>
        <div>
          <div className="big-reading">5,2°</div>
          <h1>
            Les réactifs restent entre <em>2 et 8 °C</em>. Nous veillons.
          </h1>
        </div>
        <div className="scale">
          −2 ··· 0 ··· <span style={{ color: '#7fe0f0' }}>2 ████████ 8</span> ··· 10 ··· 12 °C
        </div>
      </section>
      <section className="public-form">{children}</section>
    </div>
  )
}

export function LoginPage() {
  const { status, login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const target = (location.state as { from?: string } | null)?.from ?? '/'
  if (status === 'authenticated') return <Navigate to={target} replace />

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate(target, { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'E-mail ou mot de passe incorrect.'
          : describeError(err),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <PublicLayout>
      <form className="card stack" onSubmit={onSubmit} noValidate>
        <div>
          <h2>Connexion</h2>
          <p className="muted" style={{ margin: 0 }}>
            Surveillance des réfrigérateurs du laboratoire.
          </p>
        </div>
        {error ? <ErrorBox>{error}</ErrorBox> : null}
        <Field label="Adresse e-mail">
          {(id) => (
            <input
              id={id}
              className="input"
              type="email"
              autoComplete="username"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
        <Field label="Mot de passe">
          {(id) => (
            <input
              id={id}
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <button className="btn btn-primary btn-block" disabled={busy || !email || !password}>
          {busy ? 'Connexion…' : 'Se connecter'}
        </button>
        <Link to="/mot-de-passe-oublie" style={{ fontSize: 14, textAlign: 'center' }}>
          Mot de passe oublié ?
        </Link>
      </form>
    </PublicLayout>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const data = await api<{ detail: string }>('/api/auth/password/reset/', {
        method: 'POST',
        body: { email },
      })
      setSent(data.detail)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <PublicLayout>
      <form className="card stack" onSubmit={onSubmit} noValidate>
        <div>
          <h2>Mot de passe oublié</h2>
          <p className="muted" style={{ margin: 0 }}>
            Un lien pour choisir un nouveau mot de passe vous sera envoyé.
          </p>
        </div>
        {sent ? <div className="alert-box success">{sent}</div> : null}
        {error ? <ErrorBox>{error}</ErrorBox> : null}
        <Field label="Adresse e-mail">
          {(id) => (
            <input
              id={id}
              className="input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
        <button className="btn btn-primary btn-block" disabled={busy || !email}>
          {busy ? 'Envoi…' : 'Envoyer le lien'}
        </button>
        <Link to="/connexion" style={{ fontSize: 14, textAlign: 'center' }}>
          Retour à la connexion
        </Link>
      </form>
    </PublicLayout>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const mismatch = confirm.length > 0 && confirm !== password

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (mismatch) return
    setBusy(true)
    setError(null)
    setFieldError(undefined)
    try {
      await api('/api/auth/password/reset/confirm/', {
        method: 'POST',
        body: { uid: params.get('uid'), token: params.get('token'), new_password: password },
      })
      setDone(true)
    } catch (err) {
      const fields = fieldErrors(err)
      if (fields.new_password) setFieldError(fields.new_password)
      else setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <PublicLayout>
      {done ? (
        <div className="card stack">
          <h2>Mot de passe modifié</h2>
          <div className="alert-box success">Vous pouvez maintenant vous connecter.</div>
          <Link to="/connexion" className="btn btn-primary btn-block">
            Se connecter
          </Link>
        </div>
      ) : (
        <form className="card stack" onSubmit={onSubmit} noValidate>
          <h2>Nouveau mot de passe</h2>
          {error ? <ErrorBox>{error}</ErrorBox> : null}
          <Field label="Nouveau mot de passe" error={fieldError} hint="8 caractères minimum, pas trop courant.">
            {(id, describedBy) => (
              <input
                id={id}
                className="input"
                type="password"
                autoComplete="new-password"
                aria-describedby={describedBy}
                aria-invalid={Boolean(fieldError)}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <Field label="Confirmation" error={mismatch ? 'Les deux mots de passe diffèrent.' : undefined}>
            {(id, describedBy) => (
              <input
                id={id}
                className="input"
                type="password"
                autoComplete="new-password"
                aria-describedby={describedBy}
                aria-invalid={mismatch}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            )}
          </Field>
          <button className="btn btn-primary btn-block" disabled={busy || !password || mismatch}>
            {busy ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </form>
      )}
    </PublicLayout>
  )
}
