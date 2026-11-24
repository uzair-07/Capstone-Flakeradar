import { useEffect, useState } from 'react'
import { api, ApiError, type Project, type User } from './api'
import { AuthPage } from './components/AuthPage'
import { NewProjectForm } from './components/NewProjectForm'
import { Notice } from './components/Notice'
import { RunDetailPage } from './components/RunDetailPage'
import { RunsPage } from './components/RunsPage'
import { SettingsPage } from './components/SettingsPage'
import { TestDetailPage } from './components/TestDetailPage'
import { TestsPage } from './components/TestsPage'

const PROJECT_KEY = 'flakeradar.project'
const UUID = '([0-9a-f-]{36})'

type Route =
  | { page: 'runs' }
  | { page: 'run'; id: string }
  | { page: 'tests' }
  | { page: 'test'; id: string }
  | { page: 'settings' }

function parseRoute(hash: string): Route {
  const run = hash.match(new RegExp(`^#/runs/${UUID}$`, 'i'))
  if (run) return { page: 'run', id: run[1] }
  const test = hash.match(new RegExp(`^#/tests/${UUID}$`, 'i'))
  if (test) return { page: 'test', id: test[1] }
  if (hash === '#/tests') return { page: 'tests' }
  if (hash === '#/settings') return { page: 'settings' }
  return { page: 'runs' }
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

type Session = { state: 'checking' } | { state: 'anonymous' } | { state: 'signed-in'; user: User }

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [session, setSession] = useState<Session>({ state: 'checking' })
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
      .me(controller.signal)
      .then((user) => setSession({ state: 'signed-in', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) setSession({ state: 'anonymous' })
        else if (err instanceof ApiError) setError(err)
      })
    return () => controller.abort()
  }, [])

  const signedIn = session.state === 'signed-in'
  useEffect(() => {
    if (!signedIn) return
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
  }, [signedIn])

  const chooseProject = (next: string) => {
    setSlug(next)
    storeProject(next)
    if (route.page === 'run' || route.page === 'test') window.location.hash = ''
  }

  const addProject = (project: Project) => {
    setProjects((list) => [...(list ?? []), project])
    chooseProject(project.slug)
    window.location.hash = '#/settings'
  }

  const logout = async () => {
    try {
      await api.logout()
    } finally {
      setSession({ state: 'anonymous' })
      setProjects(null)
    }
  }

  const tab = route.page === 'run' ? 'runs' : route.page === 'test' ? 'tests' : route.page

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
        {signedIn && projects && projects.length > 0 && (
          <nav className="tabs" aria-label="Sections">
            <a href="#" className={tab === 'runs' ? 'active' : undefined}>
              Runs
            </a>
            <a href="#/tests" className={tab === 'tests' ? 'active' : undefined}>
              Tests
            </a>
            <a href="#/settings" className={tab === 'settings' ? 'active' : undefined}>
              Settings
            </a>
          </nav>
        )}
        {signedIn && (
          <div className="account">
            {projects && projects.length > 0 && (
              <label className="project-picker">
                <span>Project</span>
                <select
                  id="project"
                  value={slug ?? ''}
                  onChange={(e) => chooseProject(e.target.value)}
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.slug}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span className="muted small">{session.user.email}</span>
            <button type="button" onClick={logout}>
              Log out
            </button>
          </div>
        )}
      </header>

      <main className="content">
        {error && (
          <Notice tone="critical" title="The API is not available">
            {error.message}
          </Notice>
        )}
        {!error && session.state === 'checking' && <p className="muted">Loading…</p>}
        {!error && session.state === 'anonymous' && (
          <AuthPage onSignedIn={(user) => setSession({ state: 'signed-in', user })} />
        )}
        {!error && signedIn && projects?.length === 0 && (
          <Notice title="Create your first project">
            A project collects the test reports of one repository.
            <NewProjectForm onCreated={addProject} />
          </Notice>
        )}
        {!error && signedIn && slug && projects && projects.length > 0 && (
          <>
            {route.page === 'runs' && <RunsPage key={slug} slug={slug} />}
            {route.page === 'run' && <RunDetailPage id={route.id} />}
            {route.page === 'tests' && <TestsPage key={slug} slug={slug} />}
            {route.page === 'test' && <TestDetailPage id={route.id} />}
            {route.page === 'settings' && (
              <>
                <SettingsPage key={slug} slug={slug} />
                <h2 className="section-title">New project</h2>
                <NewProjectForm onCreated={addProject} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}
