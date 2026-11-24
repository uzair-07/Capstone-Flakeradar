"""Tests of a project with their flakiness score, and one test's history."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Float, cast, func, or_, select
from sqlalchemy.orm import Session

from app.analytics.scoring import (
    MIN_RUNS_FOR_SUGGESTION,
    SUGGEST_THRESHOLD,
    FlakinessStats,
    explain,
)
from app.auth.service import current_user, owned_project
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import CiRun, Project, TestCase, TestCaseStats, TestResult, User

router = APIRouter(tags=["tests"])

HISTORY_LIMIT = 50


class TestSummary(BaseModel):
    __test__ = False

    id: uuid.UUID
    suite: str
    classname: str
    name: str
    file: str | None
    runs: int
    failures: int
    failure_rate: float
    flips: int
    contradiction_commits: int
    retried_runs: int
    score: float
    suggest_quarantine: bool
    reason: str
    last_status: str | None
    last_run_at: datetime | None


class TestPage(BaseModel):
    __test__ = False

    items: list[TestSummary]
    total: int


class HistoryPoint(BaseModel):
    run_id: uuid.UUID
    started_at: datetime
    branch: str | None
    commit_sha: str | None
    status: str
    duration_ms: int
    retried: bool
    failure_message: str | None


class TestDetail(TestSummary):
    project_slug: str
    history: list[HistoryPoint]


def _summary(case: TestCase, stats: TestCaseStats | None) -> TestSummary:
    s = _as_stats(stats)
    return TestSummary(
        id=case.id,
        suite=case.suite,
        classname=case.classname,
        name=case.name,
        file=case.file,
        runs=s.runs,
        failures=s.failures,
        failure_rate=round(s.failure_rate, 4),
        flips=s.flips,
        contradiction_commits=s.contradiction_commits,
        retried_runs=s.retried_runs,
        score=s.score,
        suggest_quarantine=s.suggest_quarantine,
        reason=explain(s),
        last_status=s.last_status,
        last_run_at=s.last_run_at,
    )


def _as_stats(row: TestCaseStats | None) -> FlakinessStats:
    if row is None:
        return FlakinessStats(0, 0, 0, 0, 0.0, 0, 0, 0, 0.0, None, None)
    return FlakinessStats(
        runs=row.runs,
        passes=row.passes,
        failures=row.failures,
        flips=row.flips,
        flip_rate=row.flip_rate,
        commits=row.commits,
        contradiction_commits=row.contradiction_commits,
        retried_runs=row.retried_runs,
        score=row.score,
        last_status=row.last_status,
        last_run_at=row.last_run_at,
    )


@router.get("/projects/{project_slug}/tests", response_model=TestPage, summary="Tests by score")
def list_tests(
    project_slug: str,
    sort: Literal["score", "failure_rate", "name", "recent"] = "score",
    q: Annotated[str | None, Query(max_length=200)] = None,
    flaky_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TestPage:
    project = owned_project(db, user, project_slug)
    query = (
        select(TestCase, TestCaseStats)
        .outerjoin(TestCaseStats, TestCaseStats.test_case_id == TestCase.id)
        .where(TestCase.project_id == project.id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(TestCase.name.ilike(pattern), TestCase.classname.ilike(pattern)))
    if flaky_only:
        query = query.where(
            TestCaseStats.score >= SUGGEST_THRESHOLD,
            TestCaseStats.runs >= MIN_RUNS_FOR_SUGGESTION,
        )

    failure_rate = cast(TestCaseStats.failures, Float) / func.nullif(TestCaseStats.runs, 0)
    order = {
        "score": [TestCaseStats.score.desc().nulls_last(), TestCaseStats.failures.desc()],
        "failure_rate": [failure_rate.desc().nulls_last(), TestCaseStats.score.desc()],
        "name": [TestCase.classname, TestCase.name],
        "recent": [TestCaseStats.last_run_at.desc().nulls_last()],
    }[sort]

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(*order, TestCase.id).limit(limit).offset(offset)).all()
    return TestPage(items=[_summary(case, stats) for case, stats in rows], total=total)


@router.get("/tests/{test_id}", response_model=TestDetail, summary="One test and its history")
def get_test(
    test_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> TestDetail:
    case = db.get(TestCase, test_id)
    project = db.get(Project, case.project_id) if case else None
    if case is None or project is None or project.owner_id != user.id:
        raise NotFoundError("No test with this ID.")
    stats = db.get(TestCaseStats, case.id)
    rows = db.execute(
        select(TestResult, CiRun)
        .join(CiRun, CiRun.id == TestResult.run_id)
        .where(TestResult.test_case_id == case.id)
        .order_by(CiRun.started_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    history = [
        HistoryPoint(
            run_id=run.id,
            started_at=run.started_at,
            branch=run.branch,
            commit_sha=run.commit_sha,
            status=result.status,
            duration_ms=result.duration_ms,
            retried=result.retried,
            failure_message=result.failure_message,
        )
        for result, run in rows
    ]
    return TestDetail(
        **_summary(case, stats).model_dump(), project_slug=project.slug, history=history
    )
