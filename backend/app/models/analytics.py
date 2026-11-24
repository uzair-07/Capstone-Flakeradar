import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TestCaseStats(Base):
    """Precomputed flakiness signals per test, refreshed after every processed upload."""

    __test__ = False
    __tablename__ = "test_case_stats"
    __table_args__ = (Index("ix_test_case_stats_project_score", "project_id", "score"),)

    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    runs: Mapped[int] = mapped_column(Integer, default=0)
    passes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    flips: Mapped[int] = mapped_column(Integer, default=0)
    flip_rate: Mapped[float] = mapped_column(Double, default=0.0)
    commits: Mapped[int] = mapped_column(Integer, default=0)
    contradiction_commits: Mapped[int] = mapped_column(Integer, default=0)
    retried_runs: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Double, default=0.0)
    last_status: Mapped[str | None] = mapped_column(String(10))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
