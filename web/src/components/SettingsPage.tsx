import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type ApiToken, type NewApiToken } from '../api'
import { absoluteTime, timeAgo } from '../format'
import { Notice } from './Notice'

export function SettingsPage({ slug }: { slug: string }) {
  const [tokens, setTokens] = useState<ApiToken[] | null>(null)
  const [created, setCreated] = useState<NewApiToken | null>(null)
  const [name, setName] = useState('ci')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [confirming, setConfirming] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .tokens(slug)
      .then(setTokens)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load tokens.'))
  }, [slug])

  useEffect(load, [load])

  const create = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setCopied(false)
    try {
      setCreated(await api.createToken(slug, name.trim() || 'ci'))
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the token.')
    }
  }

  const revoke = async (id: string) => {
    setConfirming(null)
    try {
      await api.revokeToken(slug, id)
      if (created?.id === id) setCreated(null)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not revoke the token.')
    }
  }

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const command = `flakeradar-upload "reports/**/*.xml" --server ${window.location.origin} --project ${slug}`

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted">CI tokens let your pipelines upload test reports to this project.</p>
        </div>
      </div>

      {error && <Notice tone="critical" title="Something went wrong">{error}</Notice>}

      {created && (
        <section className="notice notice-success" role="status">
          <h2>Token “{created.name}” created</h2>
          <p className="notice-body">
            Copy it now and store it as the <code>FLAKERADAR_TOKEN</code> secret in your CI. It
            will not be shown again.
          </p>
          <div className="token-row">
            <code className="token-value">{created.token}</code>
            <button type="button" onClick={() => copy(created.token)}>
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </section>
      )}

      <form className="inline-form" onSubmit={create}>
        <label htmlFor="token-name">Token name</label>
        <input
          id="token-name"
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit" className="primary">
          Create token
        </button>
      </form>

      {tokens && tokens.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Token</th>
                <th scope="col">Created</th>
                <th scope="col">Last used</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} className={t.revoked_at ? 'revoked' : undefined}>
                  <td>{t.name}</td>
                  <td className="mono">fr_{t.prefix}_…</td>
                  <td title={absoluteTime(t.created_at)}>{timeAgo(t.created_at)}</td>
                  <td>{t.last_used_at ? timeAgo(t.last_used_at) : 'never'}</td>
                  <td className="num">
                    {t.revoked_at ? (
                      <span className="muted">revoked</span>
                    ) : confirming === t.id ? (
                      <>
                        <button type="button" className="danger" onClick={() => revoke(t.id)}>
                          Confirm revoke
                        </button>{' '}
                        <button type="button" onClick={() => setConfirming(null)}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button type="button" onClick={() => setConfirming(t.id)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section-title">Upload from CI</h2>
      <p className="muted">After your tests run, add this step with the token as an environment variable:</p>
      <pre>{command}</pre>
    </>
  )
}
