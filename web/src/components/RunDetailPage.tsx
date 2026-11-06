import { useEffect, useState } from 'react'
import { api, ApiError, type RunDetail } from '../api'
import { absoluteTime, formatDuration, shortSha } from '../format'
import { Notice } from './Notice'
import { StatusPill } from './StatusPill'

export function RunDetailPage({ id }: { id: string }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setRun(null)
    setError(null)
    api
      .run(id, controller.signal)
      .then(setRun)
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message)
      })
    return () => controller.abort()
  }, [id])

  if (error) return <Notice tone="critical" title="Could not load this run">{error}</Notice>
  if (!run) return <p className="muted">Loading…</p>

  const counts = [
    { label: 'passed', value: run.passed, cls: 'passed' },
    { label: 'failed', value: run.failed, cls: 'failed' },
    { label: 'errors', value: run.errored, cls: 'error' },
    { label: 'skipped', value: run.skipped, cls: 'skipped' },
  ]

  return (
    <>
      <a className="back" href="#">
        ← All runs
      </a>
      <div className="page-head">
        <div>
          <h1>
            Run on <span className="branch">{run.branch ?? 'unknown branch'}</span>
          </h1>
          <p className="muted">
            Commit <span className="mono">{shortSha(run.commit_sha)}</span>
            {run.ci_run_id && <> · CI run {run.ci_run_id}{run.attempt > 1 && ` (attempt ${run.attempt})`}</>}
            {' · '}
            {absoluteTime(run.started_at)} · {formatDuration(run.duration_ms)}
          </p>
        </div>
      </div>

      <ul className="counts" aria-label="Result counts">
        {counts.map((c) => (
          <li key={c.label} className={`count count-${c.cls}`}>
            <strong>{c.value}</strong> {c.label}
          </li>
        ))}
      </ul>

      <div className="table-wrap">
        <table className="results">
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col" className="wide">Test</th>
              <th scope="col" className="num">Duration</th>
            </tr>
          </thead>
          <tbody>
            {run.results.map((r) => (
              <tr key={r.test_case_id}>
                <td>
                  <StatusPill status={r.status} />
                </td>
                <td className="wide">
                  <div className="test-name">
                    {r.name}
                    {r.retried && (
                      <span className="tag" title="The report shows this test needed a retry to pass">
                        retried
                      </span>
                    )}
                  </div>
                  {r.classname && <div className="muted small mono">{r.classname}</div>}
                  {r.failure_message && (
                    <details>
                      <summary>Failure output</summary>
                      <pre>{r.failure_message}</pre>
                    </details>
                  )}
                </td>
                <td className="num">{formatDuration(r.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
