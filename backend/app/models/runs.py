import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TestStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class CiRun(Base):
    """The results of one uploaded report. A CI job that uploads three files has three runs
    sharing the same commit, branch and ci_run_id."""

    __tablename__ = "ci_runs"
    __table_args__ = (
        Index("ix_ci_runs_project_started", "project_id", "started_at", "id"),
        Index("ix_ci_runs_project_commit", "project_id", "commit_sha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), unique=True
    )
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    branch: Mapped[str | None] = mapped_column(String(255))
    ci_run_id: Mapped[str | None] = mapped_column(String(255))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    errored: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestCase(Base):
    """A test's stable identity within a project (classname + name)."""

    __test__ = False  # stop pytest from collecting this class
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("project_id", "identity_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    suite: Mapped[str] = mapped_column(String(500), default="")
    classname: Mapped[str] = mapped_column(String(500), default="")
    name: Mapped[str] = mapped_column(String(1000))
    file: Mapped[str | None] = mapped_column(String(1000))
    identity_hash: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TestResult(Base):
    __test__ = False
    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_case_run", "test_case_id", "run_id"),
        Index("ix_test_results_run", "run_id"),
        CheckConstraint(
            "status IN ('passed', 'failed', 'error', 'skipped')", name="status_valid"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ci_runs.id", ondelete="CASCADE"))
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(10))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    # True when the report shows the test needed a retry (e.g. surefire flakyFailure).
    retried: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_message: Mapped[str | None] = mapped_column(Text)
