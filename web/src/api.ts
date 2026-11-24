// Typed client for the FlakeRadar API. Shapes mirror backend/app/runs/schemas.py.

export interface Project {
  id: string
  name: string
  slug: string
  default_branch: string
  created_at: string
}

export interface RunSummary {
  id: string
  commit_sha: string | null
  branch: string | null
  ci_run_id: string | null
  attempt: number
  started_at: string
  total: number
  passed: number
  failed: number
  errored: number
  skipped: number
  duration_ms: number
}

export interface RunPage {
  items: RunSummary[]
  next_cursor: string | null
}

export type TestStatus = 'passed' | 'failed' | 'error' | 'skipped'

export interface TestResultRow {
  test_case_id: string
  suite: string
  classname: string
  name: string
  file: string | null
  status: TestStatus
  duration_ms: number
  retried: boolean
  failure_message: string | null
}

export interface RunDetail extends RunSummary {
  project_slug: string
  results: TestResultRow[]
}

export class ApiError extends Error {
  readonly status: number
  readonly requestId?: string

  constructor(status: number, message: string, requestId?: string) {
    super(message)
    this.status = status
    this.requestId = requestId
  }
}

export interface User {
  id: string
  email: string
  created_at: string
}

export interface TestSummary {
  id: string
  suite: string
  classname: string
  name: string
  file: string | null
  runs: number
  failures: number
  failure_rate: number
  flips: number
  contradiction_commits: number
  retried_runs: number
  score: number
  suggest_quarantine: boolean
  reason: string
  last_status: TestStatus | null
  last_run_at: string | null
}

export interface TestPage {
  items: TestSummary[]
  total: number
}

export interface HistoryPoint {
  run_id: string
  started_at: string
  branch: string | null
  commit_sha: string | null
  status: TestStatus
  duration_ms: number
  retried: boolean
  failure_message: string | null
}

export interface TestDetail extends TestSummary {
  project_slug: string
  history: HistoryPoint[]
}

export interface ApiToken {
  id: string
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export interface NewApiToken extends ApiToken {
  token: string
}

export type TestSort = 'score' | 'failure_rate' | 'name' | 'recent'

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      signal,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the FlakeRadar API. Check that the server is running.')
  }
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`
    let requestId: string | undefined
    try {
      const data = await response.json()
      detail = data.detail ?? detail
      requestId = data.request_id
    } catch {
      // not a problem-details body
    }
    throw new ApiError(response.status, detail, requestId)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const getJson = <T,>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal)
const slugPath = (slug: string) => `/api/v1/projects/${encodeURIComponent(slug)}`

export const api = {
  me: (signal?: AbortSignal) => getJson<User>('/api/v1/auth/me', signal),
  register: (email: string, password: string) =>
    request<User>('POST', '/api/v1/auth/register', { email, password }),
  login: (email: string, password: string) =>
    request<User>('POST', '/api/v1/auth/login', { email, password }),
  logout: () => request<void>('POST', '/api/v1/auth/logout'),

  projects: (signal?: AbortSignal) => getJson<Project[]>('/api/v1/projects', signal),
  createProject: (name: string, slug?: string) =>
    request<Project>('POST', '/api/v1/projects', { name, slug: slug || undefined }),

  tokens: (slug: string, signal?: AbortSignal) =>
    getJson<ApiToken[]>(`${slugPath(slug)}/tokens`, signal),
  createToken: (slug: string, name: string) =>
    request<NewApiToken>('POST', `${slugPath(slug)}/tokens`, { name }),
  revokeToken: (slug: string, id: string) =>
    request<void>('DELETE', `${slugPath(slug)}/tokens/${encodeURIComponent(id)}`),

  runs: (slug: string, opts: { cursor?: string | null; branch?: string }, signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: '25' })
    if (opts.cursor) params.set('cursor', opts.cursor)
    if (opts.branch) params.set('branch', opts.branch)
    return getJson<RunPage>(`${slugPath(slug)}/runs?${params}`, signal)
  },
  run: (id: string, signal?: AbortSignal) =>
    getJson<RunDetail>(`/api/v1/runs/${encodeURIComponent(id)}`, signal),

  tests: (
    slug: string,
    opts: { sort: TestSort; q?: string; flakyOnly?: boolean; offset?: number },
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams({ sort: opts.sort, limit: '50' })
    if (opts.q) params.set('q', opts.q)
    if (opts.flakyOnly) params.set('flaky_only', 'true')
    if (opts.offset) params.set('offset', String(opts.offset))
    return getJson<TestPage>(`${slugPath(slug)}/tests?${params}`, signal)
  },
  test: (id: string, signal?: AbortSignal) =>
    getJson<TestDetail>(`/api/v1/tests/${encodeURIComponent(id)}`, signal),
}
