import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type RunSummary } from '../api'
import { absoluteTime, formatDuration, shortSha, timeAgo } from '../format'
import { Notice } from './Notice'
import { ResultBar } from './ResultBar'

export function RunsPage({ slug }: { slug: string }) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [branch, setBranch] = useState('')
  const [appliedBranch, setAppliedBranch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    async (from: string | null, signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const page = await api.runs(slug, { cursor: from, branch: appliedBranch || undefined }, signal)
        setRuns((prev) => (from ? [...prev, ...page.items] : page.items))
        setCursor(page.next_cursor)
      } catch (err) {
        if (err instanceof ApiError) setError(err.message)
        else if (!(err instanceof DOMException)) setError('Could not load runs.')
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [slug, appliedBranch],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(null, controller.signal)
    return () => controller.abort()
  }, [load])

  const failing = runs.filter((run) => run.failed + run.errored > 0).length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p className="muted">
            {runs.length === 0
              ? 'Test reports uploaded from CI appear here.'
              : `${runs.length}${cursor ? '+' : ''} runs shown, ${failing} with failures.`}
          </p>
        </div>
        <form
          className="filter"
          onSubmit={(e) => {
            e.preventDefault()
            setAppliedBranch(branch.trim())
          }}
        >
          <label htmlFor="branch">Branch</label>
          <input
            id="branch"
            value={branch}
            placeholder="all branches"
            onChange={(e) => setBranch(e.target.value)}
          />
          <button type="submit">Filter</button>
        </form>
      </div>

      {error && <Notice tone="critical" title="Could not load runs">{error}</Notice>}

      {!error && !loading && runs.length === 0 && (
        <Notice title={appliedBranch ? `No runs on ${appliedBranch}` : 'No runs yet'}>
          Upload a JUnit XML report with the uploader, for example:
          <pre>{`flakeradar-upload report.xml --server http://localhost:8080 \\
  --project ${slug} --token $FLAKERADAR_TOKEN --wait`}</pre>
        </Notice>
      )}

      {runs.length > 0 && (
        <div className="table-wrap">
          <table className="runs">
            <thead>
              <tr>
                <th scope="col">Started</th>
                <th scope="col">Branch</th>
                <th scope="col">Commit</th>
                <th scope="col" className="wide">Results</th>
                <th scope="col" className="num">Tests</th>
                <th scope="col" className="num">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const bad = run.failed + run.errored
                return (
                  <tr key={run.id} className={bad > 0 ? 'has-failures' : undefined}>
                    <td>
                      <a href={`#/runs/${run.id}`} title={absoluteTime(run.started_at)}>
                        {timeAgo(run.started_at)}
                      </a>
                    </td>
                    <td className="branch">{run.branch ?? '—'}</td>
                    <td className="mono">{shortSha(run.commit_sha)}</td>
                    <td className="wide">
                      <div className="results-cell">
                        <ResultBar run={run} />
                        <span className={bad > 0 ? 'fail-count' : 'ok-count'}>
                          {bad > 0 ? `${bad} failing` : 'all passed'}
                        </span>
                      </div>
                    </td>
                    <td className="num">{run.total}</td>
                    <td className="num">{formatDuration(run.duration_ms)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {loading && <p className="muted">Loading…</p>}
      {cursor && !loading && (
        <button className="more" type="button" onClick={() => load(cursor)}>
          Load older runs
        </button>
      )}
    </>
  )
}
