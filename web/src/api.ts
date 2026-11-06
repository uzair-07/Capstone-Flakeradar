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

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the FlakeRadar API. Check that the server is running.')
  }
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`
    let requestId: string | undefined
    try {
      const body = await response.json()
      detail = body.detail ?? detail
      requestId = body.request_id
    } catch {
      // not a problem-details body
    }
    throw new ApiError(response.status, detail, requestId)
  }
  return (await response.json()) as T
}

export const api = {
  projects: (signal?: AbortSignal) => getJson<Project[]>('/api/v1/projects', signal),

  runs: (slug: string, opts: { cursor?: string | null; branch?: string }, signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: '25' })
    if (opts.cursor) params.set('cursor', opts.cursor)
    if (opts.branch) params.set('branch', opts.branch)
    return getJson<RunPage>(`/api/v1/projects/${encodeURIComponent(slug)}/runs?${params}`, signal)
  },

  run: (id: string, signal?: AbortSignal) =>
    getJson<RunDetail>(`/api/v1/runs/${encodeURIComponent(id)}`, signal),
}
