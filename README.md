# FlakeRadar

Find, explain and quarantine flaky tests from your CI results.

FlakeRadar collects the JUnit XML reports your test runs already produce, stores every test's
history, and (from Sprint 2) scores how flaky each test is so you can quarantine it instead of
re-running red builds.

> **Status: Sprint 2 done (24 Nov 2026).** Reports are uploaded from CI, parsed in the
> background and scored: the Tests page ranks tests by an explainable flakiness score.
> Accounts, projects and CI tokens are managed in the web app. Quarantine and
> `quarantine.json` follow in Sprint 3. See [evaluation/](evaluation/) for measured accuracy.

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

Then:

1. Open **http://localhost:8080**, create an account and a project.
2. In **Settings**, create a CI token and copy it.
3. Upload reports (any machine with Python 3.10+):

```bash
pip install ./uploader
flakeradar-upload backend/tests/fixtures/junit/pytest.xml \
  --server http://localhost:8080 --project <project slug> --token <token> --wait

# or 60 commits of simulated history with known flaky tests:
python evaluation/simulate.py --commits 60 --server http://localhost:8080 \
  --project <project slug> --token <token>
```

The **Tests** page then ranks tests by flakiness score, each with the reason. API
documentation is at **http://localhost:8080/api/docs**.

Projects created with the admin CLI before accounts existed have no owner. After registering,
run `docker compose exec api python -m app.cli claim-projects --owner you@example.com`.

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
| `POST /api/v1/auth/register`, `/login`, `/logout`, `GET /auth/me` | session cookie | Accounts |
| `GET/POST /api/v1/projects` | session | Your projects |
| `GET/POST /api/v1/projects/{slug}/tokens`, `DELETE .../tokens/{id}` | session | CI tokens (plain token shown once) |
| `GET /api/v1/projects/{slug}/runs?limit=&cursor=&branch=` | session | Runs, newest first, cursor-paginated |
| `GET /api/v1/runs/{id}` | session | One run with its results, failures first |
| `GET /api/v1/projects/{slug}/tests?sort=score&q=&flaky_only=` | session | Tests with flakiness score and reason |
| `GET /api/v1/tests/{id}` | session | One test with its recent history |
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
| 1 | 26 Oct – 8 Nov | Walking skeleton: upload → parse → store → Runs page ✅ |
| 2 | 9 – 22 Nov | Accounts, token management, flakiness score v1, demo suite, deployment setup ✅ (24 Nov) |
| 3 | 23 Nov – 6 Dec | Quarantine and `quarantine.json`, live deployment (MVP) |
| 4 | 7 – 20 Dec | Score tuning against the benchmark, performance at 1 M results, security review |

## How the flakiness score works

For each test's last 30 results (`backend/app/analytics/scoring.py`):

- **Same-commit contradictions**: commits where the test both passed and failed, plus runs
  the report marks as retried. The strongest evidence of flakiness.
- **Flip rate**: how often the result switches between pass and fail on the main branch.
  A test broken by a real bug fails consistently and flips rarely.

`score = min(1, 0.6 × contradiction ratio + 0.4 × flip rate)`. Tests with at least 10 runs and a
score of 0.15 or more are suggested for quarantine. Every score comes with a one-sentence
reason, for example: "Passed and failed on the same commit 4 times; switched between pass and
fail 7 times on the main branch (4 of 16 runs failed)."

## Deployment

See [docs/deploy.md](docs/deploy.md): one server, Docker Compose, automatic HTTPS, and a
GitHub Actions workflow that deploys `main` after CI passes.

## License

MIT
