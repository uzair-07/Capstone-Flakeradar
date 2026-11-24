import { useState, type FormEvent } from 'react'
import { api, ApiError, type User } from '../api'

export function AuthPage({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user =
        mode === 'login' ? await api.login(email, password) : await api.register(email, password)
      onSignedIn(user)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth">
      <h1>{mode === 'login' ? 'Log in to FlakeRadar' : 'Create your account'}</h1>
      <p className="muted">
        {mode === 'login'
          ? 'See which of your tests are flaky, and why.'
          : 'Use at least 10 characters for your password.'}
      </p>
      <form onSubmit={submit} className="stack">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          minLength={mode === 'register' ? 10 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>
      </form>
      <p className="muted small">
        {mode === 'login' ? 'New here? ' : 'Already have an account? '}
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
        >
          {mode === 'login' ? 'Create an account' : 'Log in'}
        </button>
      </p>
    </section>
  )
}
