import { useEffect, useState } from 'react'
import { api, ApiError, type Project } from './api'
import { RunsPage } from './components/RunsPage'
import { RunDetailPage } from './components/RunDetailPage'
import { Notice } from './components/Notice'

const PROJECT_KEY = 'flakeradar.project'

type Route = { page: 'runs' } | { page: 'run'; id: string }

function parseRoute(hash: string): Route {
  const match = hash.match(/^#\/runs\/([0-9a-f-]{36})$/i)
  return match ? { page: 'run', id: match[1] } : { page: 'runs' }
}

function readStoredProject(): string | null {
  try {
    return localStorage.getItem(PROJECT_KEY)
  } catch {
    return null
  }
}

function storeProject(slug: string) {
  try {
    localStorage.setItem(PROJECT_KEY, slug)
  } catch {
    // storage unavailable; the choice just isn't remembered
  }
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [slug, setSlug] = useState<string | null>(readStoredProject)

  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api
      .projects(controller.signal)
      .then((list) => {
        setProjects(list)
        setSlug((current) =>
          current && list.some((p) => p.slug === current) ? current : (list[0]?.slug ?? null),
        )
      })
      .catch((err) => {
        if (err instanceof ApiError) setError(err)
      })
    return () => controller.abort()
  }, [])

  const chooseProject = (next: string) => {
    setSlug(next)
    storeProject(next)
    window.location.hash = ''
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <circle cx="16" cy="16" r="13" />
            <circle cx="16" cy="16" r="6.5" />
            <circle className="blip" cx="16" cy="16" r="2.5" />
          </svg>
          FlakeRadar
        </a>
        {projects && projects.length > 0 && (
          <label className="project-picker">
            <span>Project</span>
            <select id="project" value={slug ?? ''} onChange={(e) => chooseProject(e.target.value)}>
              {projects.map((p) => (
                <option key={p.id} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      <main className="content">
        {error && (
          <Notice tone="critical" title="The API is not available">
            {error.message}
          </Notice>
        )}
        {!error && projects === null && <p className="muted">Loading…</p>}
        {!error && projects?.length === 0 && (
          <Notice title="No projects yet">
            Create one on the server, then upload a report:
            <pre>docker compose exec api python -m app.cli create-project --name "Demo"</pre>
          </Notice>
        )}
        {!error && slug && route.page === 'runs' && <RunsPage key={slug} slug={slug} />}
        {!error && route.page === 'run' && <RunDetailPage id={route.id} />}
      </main>
    </div>
  )
}
