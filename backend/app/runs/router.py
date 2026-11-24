"""Runs of a project, visible only to the project's owner."""

import base64
import binascii
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, or_, select
from sqlalchemy.orm import Session

from app.auth.service import current_user, owned_project
from app.core.errors import AppError, NotFoundError
from app.db.session import get_db
from app.models import CiRun, Project, TestCase, TestResult, User
from app.runs.schemas import ResultOut, RunDetail, RunPage, RunSummary

router = APIRouter(tags=["runs"])

STATUS_ORDER = case(
    (TestResult.status == "failed", 0),
    (TestResult.status == "error", 1),
    (TestResult.status == "skipped", 3),
    else_=2,
)


def _encode_cursor(run: CiRun) -> str:
    raw = f"{run.started_at.isoformat()}|{run.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        started, run_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(started), uuid.UUID(run_id)
    except (ValueError, binascii.Error) as exc:
        raise AppError("The cursor is not valid. Start again without one.") from exc


@router.get("/projects/{project_slug}/runs", response_model=RunPage, summary="Runs, newest first")
def list_runs(
    project_slug: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
    branch: Annotated[str | None, Query(max_length=255)] = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RunPage:
    project = owned_project(db, user, project_slug)
    query = select(CiRun).where(CiRun.project_id == project.id)
    if branch:
        query = query.where(CiRun.branch == branch)
    if cursor:
        started, run_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                CiRun.started_at < started,
                and_(CiRun.started_at == started, CiRun.id < run_id),
            )
        )
    runs = list(
        db.scalars(query.order_by(CiRun.started_at.desc(), CiRun.id.desc()).limit(limit + 1))
    )
    next_cursor = _encode_cursor(runs[limit - 1]) if len(runs) > limit else None
    return RunPage(
        items=[RunSummary.model_validate(run) for run in runs[:limit]],
        next_cursor=next_cursor,
    )


@router.get("/runs/{run_id}", response_model=RunDetail, summary="One run with its test results")
def get_run(
    run_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> RunDetail:
    run = db.get(CiRun, run_id)
    project = db.get(Project, run.project_id) if run else None
    if run is None or project is None or project.owner_id != user.id:
        raise NotFoundError("No run with this ID.")
    rows = db.execute(
        select(TestResult, TestCase)
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .where(TestResult.run_id == run.id)
        .order_by(STATUS_ORDER, TestCase.classname, TestCase.name)
    ).all()
    results = [
        ResultOut(
            test_case_id=test_case.id,
            suite=test_case.suite,
            classname=test_case.classname,
            name=test_case.name,
            file=test_case.file,
            status=result.status,
            duration_ms=result.duration_ms,
            retried=result.retried,
            failure_message=result.failure_message,
        )
        for result, test_case in rows
    ]
    summary = RunSummary.model_validate(run)
    return RunDetail(
        **summary.model_dump(),
        project_slug=project.slug,
        results=results,
    )
