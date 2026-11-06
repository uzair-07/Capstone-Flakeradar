# FlakeRadar

Find, explain and quarantine flaky tests from your CI results.

FlakeRadar collects the JUnit XML reports your test runs already produce, stores every test's
history, and (from Sprint 2) scores how flaky each test is so you can quarantine it instead of
re-running red builds.

> **Status: Sprint 1 — walking skeleton.** Reports can be uploaded from CI, parsed in the
> background and browsed on the Runs page. Accounts, flakiness scoring and quarantine come in
> the next sprints. The read endpoints have no login yet, so run it only on your own machine
> or a private network for now.

## Architecture

```
CI job ──flakeradar-upload──▶ Caddy ──/api──▶ FastAPI ──▶ PostgreSQL
                               │                │ enqueue
Browser ──────────────────────▶│ static app     ▼
                                              Redis ──▶ Worker (parse JUnit XML, store results)
```

| Part | Folder | Tech |
| --- | --- | --- |
| API | `backend/app` | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Worker | `backend/app/worker` | RQ on Redis |
| Web app | `web/` | React 18 + TypeScript (Vite), served by Caddy |
| Uploader CLI | `uploader/` | Python standard library only |
| Decisions | `docs/adr/` | Architecture decision records |

## Quick start (Docker)

Needs Docker Desktop.

```bash
docker compose up --build
```

Then, in a second terminal:

```bash
# 1. Create a project; this prints a CI token once
docker compose exec api python -m app.cli create-project --name "Demo"

# 2. Upload a sample report (any machine with Python 3.10+)
pip install ./uploader
flakeradar-upload backend/tests/fixtures/junit/pytest.xml \
  --server http://localhost:8080 --project demo --token <token from step 1> --wait
```

Open **http://localhost:8080** for the Runs page and **http://localhost:8080/api/docs** for
the API documentation.

On Windows PowerShell, put the command on one line or replace the `\` line breaks with a
backtick (`` ` ``).

## Using it from GitHub Actions

Add the token as the repository secret `FLAKERADAR_TOKEN`, then after your test step:

```yaml
- name: Upload test results to FlakeRadar
  if: always()  # upload failing runs too; that is the point
  run: |
    pip install "git+https://github.com/<owner>/flakeradar#subdirectory=uploader"
    flakeradar-upload "reports/**/*.xml" --server ${{ vars.FLAKERADAR_URL }} --project <slug>
  env:
    FLAKERADAR_TOKEN: ${{ secrets.FLAKERADAR_TOKEN }}
```

Commit, branch, run ID and attempt are detected automatically on GitHub Actions and GitLab CI.
If FlakeRadar is unreachable the uploader warns and exits 0, so it never breaks your build
(use `--fail-on-error` to change that).

## API (v1)

| Method and path | Auth | Purpose |
| --- | --- | --- |
| `POST /api/v1/projects/{slug}/uploads` | project token | Upload a JUnit XML report (multipart `file`, optional `commit_sha`, `branch`, `ci_run_id`, `attempt`). Returns `202`, or `200` with `duplicate: true` if the same file was already received. |
| `GET /api/v1/uploads/{id}` | project token | Processing status: `received`, `processing`, `done` or `failed` (with a reason) |
| `GET /api/v1/projects` | none (Sprint 1) | Projects |
| `GET /api/v1/projects/{slug}/runs?limit=&cursor=&branch=` | none (Sprint 1) | Runs, newest first, cursor-paginated |
| `GET /api/v1/runs/{id}` | none (Sprint 1) | One run with its results, failures first |
| `GET /healthz`, `GET /readyz` | none | Liveness; database and queue readiness |

Errors use [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) problem details with a
`request_id` that also appears in the JSON logs.

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up -d db redis                        # from the repo root
alembic upgrade head
uvicorn app.main:app --reload                        # API on :8000
python -m app.worker                                 # worker, in another terminal
```

Tests:

```bash
ruff check .
pytest                        # unit tests only
# integration tests use a separate database and Redis DB 15:
docker compose exec db createdb -U flakeradar flakeradar_test
FLAKERADAR_DATABASE_URL=postgresql+psycopg://flakeradar:flakeradar@localhost:5432/flakeradar_test \
FLAKERADAR_REDIS_URL=redis://localhost:6379/15 pytest
```

### Web

```bash
cd web
npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
npm run lint && npm run build
```

### Workflow

- `main` is protected: every change goes through a pull request with green CI.
- Branch names: `feat/<issue>-short-name`, `fix/...`, `chore/...`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- Schema changes need an Alembic migration; CI fails if models and migrations differ.

## Roadmap

| Sprint | Dates | Goal |
| --- | --- | --- |
| 1 | 26 Oct – 8 Nov | Walking skeleton: upload → parse → store → Runs page |
| 2 | 9 – 22 Nov | Accounts and login, token management, flakiness score v1, deployment |
| 3 | 23 Nov – 6 Dec | Tests list, test history, quarantine and `quarantine.json` (MVP) |
| 4 | 7 – 20 Dec | Detector evaluation, performance at 1 M results, security review |

## License

MIT
