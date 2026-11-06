import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    default_branch: str
    created_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    commit_sha: str | None
    branch: str | None
    ci_run_id: str | None
    attempt: int
    started_at: datetime
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    duration_ms: int


class RunPage(BaseModel):
    items: list[RunSummary]
    next_cursor: str | None


class ResultOut(BaseModel):
    test_case_id: uuid.UUID
    suite: str
    classname: str
    name: str
    file: str | None
    status: str
    duration_ms: int
    retried: bool
    failure_message: str | None


class RunDetail(RunSummary):
    project_slug: str
    results: list[ResultOut]
