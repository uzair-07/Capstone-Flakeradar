import { useEffect, useState } from 'react'
import { api, ApiError, type TestPage, type TestSort } from '../api'
import { timeAgo } from '../format'
import { Notice } from './Notice'
import { ScoreBar } from './ScoreBar'
import { StatusPill } from './StatusPill'

const SORTS: { value: TestSort; label: string }[] = [
  { value: 'score', label: 'Flakiness score' },
  { value: 'failure_rate', label: 'Failure rate' },
  { value: 'recent', label: 'Last run' },
  { value: 'name', label: 'Name' },
]

export function TestsPage({ slug }: { slug: string }) {
  const [sort, setSort] = useState<TestSort>('score')
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [flakyOnly, setFlakyOnly] = useState(false)
  const [page, setPage] = useState<TestPage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    api
      .tests(slug, { sort, q: appliedQuery || undefined, flakyOnly }, controller.signal)
      .then(setPage)
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message)
      })
    return () => controller.abort()
  }, [slug, sort, appliedQuery, flakyOnly])

  const flagged = page?.items.filter((t) => t.suggest_quarantine).length ?? 0

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Tests</h1>
          <p className="muted">
            {page === null
              ? 'Loading…'
              : `${page.total} tests${flagged ? `, ${flagged} suggested for quarantine` : ''}.`}
          </p>
        </div>
        <form
          className="filter"
          onSubmit={(e) => {
            e.preventDefault()
            setAppliedQuery(query.trim())
          }}
        >
          <label htmlFor="test-search">Search</label>
          <input
            id="test-search"
            value={query}
            placeholder="test or class name"
            onChange={(e) => setQuery(e.target.value)}
          />
          <label htmlFor="test-sort">Sort</label>
          <select id="test-sort" value={sort} onChange={(e) => setSort(e.target.value as TestSort)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <label className="check">
            <input
              id="flaky-only"
              type="checkbox"
              checked={flakyOnly}
              onChange={(e) => setFlakyOnly(e.target.checked)}
            />
            Flaky only
          </label>
        </form>
      </div>

      {error && <Notice tone="critical" title="Could not load tests">{error}</Notice>}

      {page && page.items.length === 0 && !error && (
        <Notice title={flakyOnly || appliedQuery ? 'No matching tests' : 'No tests yet'}>
          Tests appear after the first report is uploaded. A test needs at least 10 runs before
          it can be suggested for quarantine.
        </Notice>
      )}

      {page && page.items.length > 0 && (
        <div className="table-wrap">
          <table className="tests">
            <thead>
              <tr>
                <th scope="col" className="wide">Test</th>
                <th scope="col">Score</th>
                <th scope="col" className="num">Runs</th>
                <th scope="col" className="num">Failed</th>
                <th scope="col">Last</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((t) => (
                <tr key={t.id} className={t.suggest_quarantine ? 'has-failures' : undefined}>
                  <td className="wide">
                    <a className="test-name" href={`#/tests/${t.id}`}>
                      {t.name}
                    </a>
                    {t.suggest_quarantine && <span className="tag">flaky</span>}
                    <div className="muted small mono">{t.classname}</div>
                    <div className="reason">{t.reason}</div>
                  </td>
                  <td>
                    <ScoreBar score={t.score} flagged={t.suggest_quarantine} />
                  </td>
                  <td className="num">{t.runs}</td>
                  <td className="num">{Math.round(t.failure_rate * 100)}%</td>
                  <td>
                    {t.last_status && <StatusPill status={t.last_status} />}
                    {t.last_run_at && <div className="muted small">{timeAgo(t.last_run_at)}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
