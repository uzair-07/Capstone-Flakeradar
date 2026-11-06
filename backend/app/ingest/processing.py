"""Turn a parsed report into a CI run, test cases and test results."""

from collections.abc import Iterable, Iterator
from typing import TypeVar

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingest.junit import ParsedReport
from app.models import CiRun, TestCase, TestResult, Upload

BATCH_SIZE = 1_000
T = TypeVar("T")


def _batches(items: list[T], size: int = BATCH_SIZE) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def store_report(db: Session, upload: Upload, report: ParsedReport) -> CiRun:
    """Insert the run and its results. The caller commits."""
    run = CiRun(
        project_id=upload.project_id,
        upload_id=upload.id,
        commit_sha=upload.commit_sha,
        branch=upload.branch,
        ci_run_id=upload.ci_run_id,
        attempt=upload.attempt,
        started_at=report.timestamp or upload.created_at,
        total=len(report.test_cases),
        passed=report.count("passed"),
        failed=report.count("failed"),
        errored=report.count("error"),
        skipped=report.count("skipped"),
        duration_ms=report.duration_ms,
    )
    db.add(run)
    db.flush()

    case_ids = _upsert_test_cases(db, upload, report)
    rows = [
        {
            "run_id": run.id,
            "test_case_id": case_ids[case.identity_hash],
            "status": case.status,
            "duration_ms": case.duration_ms,
            "retried": case.retried,
            "failure_message": case.failure_message,
        }
        for case in report.test_cases
    ]
    for batch in _batches(rows):
        db.execute(insert(TestResult), batch)
    return run


def _upsert_test_cases(db: Session, upload: Upload, report: ParsedReport) -> dict[str, object]:
    unique = {case.identity_hash: case for case in report.test_cases}
    values = [
        {
            "project_id": upload.project_id,
            "identity_hash": identity,
            "suite": case.suite[:500],
            "classname": case.classname[:500],
            "name": case.name[:1000],
            "file": case.file[:1000] if case.file else None,
        }
        for identity, case in unique.items()
    ]
    for batch in _batches(values):
        stmt = pg_insert(TestCase).values(batch)
        db.execute(stmt.on_conflict_do_nothing(index_elements=["project_id", "identity_hash"]))

    ids: dict[str, object] = {}
    for batch in _batches(list(unique)):
        ids.update(_lookup_ids(db, upload, batch))
    return ids


def _lookup_ids(db: Session, upload: Upload, hashes: Iterable[str]) -> dict[str, object]:
    rows = db.execute(
        select(TestCase.identity_hash, TestCase.id).where(
            TestCase.project_id == upload.project_id,
            TestCase.identity_hash.in_(list(hashes)),
        )
    )
    return {identity: case_id for identity, case_id in rows}
