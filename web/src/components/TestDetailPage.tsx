import { useEffect, useState } from 'react'
import { api, ApiError, type TestDetail } from '../api'
import { absoluteTime, formatDuration, shortSha } from '../format'
import { Notice } from './Notice'
import { ScoreBar } from './ScoreBar'
import { StatusPill } from './StatusPill'

export function TestDetailPage({ id }: { id: string }) {
  const [test, setTest] = useState<TestDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setTest(null)
    setError(null)
    api
      .test(id, controller.signal)
      .then(setTest)
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message)
      })
    return () => controller.abort()
  }, [id])

  if (error) return <Notice tone="critical" title="Could not load this test">{error}</Notice>
  if (!test) return <p className="muted">Loading…</p>

  // Oldest on the left, newest on the right, like a timeline.
  const timeline = [...test.history].reverse()

  return (
    <>
      <a className="back" href="#/tests">
        ← All tests
      </a>
      <div className="page-head">
        <div>
          <h1 className="test-title">
            {test.name}
            {test.suggest_quarantine && <span className="tag">suggested for quarantine</span>}
          </h1>
          <p className="muted mono small">
            {test.classname}
            {test.file && ` · ${test.file}`}
          </p>
        </div>
      </div>

      <section className="score-panel">
        <div>
          <div className="label">Flakiness score</div>
          <ScoreBar score={test.score} flagged={test.suggest_quarantine} />
        </div>
        <p className="reason-large">{test.reason}</p>
        <ul className="counts" aria-label="Signals">
          <li className="count">
            <strong>{test.runs}</strong> runs
          </li>
          <li className="count count-failed">
            <strong>{test.failures}</strong> failed
          </li>
          <li className="count">
            <strong>{test.contradiction_commits}</strong> same-commit pass and fail
          </li>
          <li className="count">
            <strong>{test.flips}</strong> flips on main
          </li>
          <li className="count">
            <strong>{test.retried_runs}</strong> retried
          </li>
        </ul>
      </section>

      <h2 className="section-title">Recent results</h2>
      <div className="timeline" role="img" aria-label="Results over time, oldest to newest">
        {timeline.map((p, i) => (
          <a
            key={`${p.run_id}-${i}`}
            href={`#/runs/${p.run_id}`}
            className={`tick tick-${p.status}${p.retried ? ' tick-retried' : ''}`}
            title={`${p.status} · ${absoluteTime(p.started_at)} · ${shortSha(p.commit_sha)}`}
          />
        ))}
      </div>
      <p className="muted small">Oldest on the left. Each mark is one run; click to open it.</p>

      <div className="table-wrap">
        <table className="results">
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col">When</th>
              <th scope="col">Branch</th>
              <th scope="col">Commit</th>
              <th scope="col" className="num">Duration</th>
            </tr>
          </thead>
          <tbody>
            {test.history.map((p, i) => (
              <tr key={`${p.run_id}-${i}`}>
                <td>
                  <StatusPill status={p.status} />
                  {p.retried && <span className="tag">retried</span>}
                </td>
                <td>
                  <a href={`#/runs/${p.run_id}`}>{absoluteTime(p.started_at)}</a>
                </td>
                <td className="branch">{p.branch ?? '—'}</td>
                <td className="mono">{shortSha(p.commit_sha)}</td>
                <td className="num">{formatDuration(p.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
