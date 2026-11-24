"""Keep test_case_stats up to date and read it back for the API."""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.analytics.scoring import WINDOW, ResultPoint, compute_stats
from app.models import CiRun, Project, TestCase, TestCaseStats, TestResult

BATCH = 500
# Skipped results are dropped before scoring, so fetch more rows than the scoring window.
FETCH_PER_TEST = WINDOW * 2


def _chunks(ids: list[uuid.UUID], size: int = BATCH) -> Iterator[list[uuid.UUID]]:
    for start in range(0, len(ids), size):
        yield ids[start : start + size]


def load_history(
    db: Session, test_case_ids: Iterable[uuid.UUID], limit: int = FETCH_PER_TEST
) -> dict[uuid.UUID, list[ResultPoint]]:
    """Most recent results per test, newest first, using one windowed query per batch."""
    history: dict[uuid.UUID, list[ResultPoint]] = defaultdict(list)
    for batch in _chunks(list(test_case_ids)):
        ranked = (
            select(
                TestResult.test_case_id,
                TestResult.status,
                TestResult.retried,
                CiRun.started_at,
                CiRun.commit_sha,
                CiRun.branch,
                func.row_number()
                .over(partition_by=TestResult.test_case_id, order_by=CiRun.started_at.desc())
                .label("rank"),
            )
            .join(CiRun, CiRun.id == TestResult.run_id)
            .where(TestResult.test_case_id.in_(batch))
            .subquery()
        )
        rows = db.execute(select(ranked).where(ranked.c.rank <= limit))
        for row in rows:
            history[row.test_case_id].append(
                ResultPoint(
                    started_at=row.started_at,
                    status=row.status,
                    commit_sha=row.commit_sha,
                    branch=row.branch,
                    retried=row.retried,
                )
            )
    return history


def recompute_stats(db: Session, project: Project, test_case_ids: Iterable[uuid.UUID]) -> int:
    """Recompute and upsert statistics for the given tests. The caller commits."""
    ids = list(dict.fromkeys(test_case_ids))
    if not ids:
        return 0
    history = load_history(db, ids)
    now = datetime.now(UTC)
    rows = []
    for case_id in ids:
        stats = compute_stats(history.get(case_id, []), default_branch=project.default_branch)
        rows.append(
            {
                "test_case_id": case_id,
                "project_id": project.id,
                "runs": stats.runs,
                "passes": stats.passes,
                "failures": stats.failures,
                "flips": stats.flips,
                "flip_rate": stats.flip_rate,
                "commits": stats.commits,
                "contradiction_commits": stats.contradiction_commits,
                "retried_runs": stats.retried_runs,
                "score": stats.score,
                "last_status": stats.last_status,
                "last_run_at": stats.last_run_at,
                "updated_at": now,
            }
        )
    for start in range(0, len(rows), BATCH):
        stmt = pg_insert(TestCaseStats).values(rows[start : start + BATCH])
        updates = {col: stmt.excluded[col] for col in rows[0] if col != "test_case_id"}
        db.execute(stmt.on_conflict_do_update(index_elements=["test_case_id"], set_=updates))
    return len(rows)


def recompute_project(db: Session, project: Project) -> int:
    ids = list(db.scalars(select(TestCase.id).where(TestCase.project_id == project.id)))
    return recompute_stats(db, project, ids)
