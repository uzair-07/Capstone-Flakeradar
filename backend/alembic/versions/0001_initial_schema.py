"""Initial schema: projects, tokens, uploads, runs, test cases and results.

Revision ID: 0001
Revises:
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", TZ, nullable=True),
        sa.Column("revoked_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_api_tokens_project_id_projects", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_api_tokens"),
        sa.UniqueConstraint("prefix", name="uq_api_tokens_prefix"),
    )
    op.create_index("ix_api_tokens_project_id", "api_tokens", ["project_id"])

    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("ci_run_id", sa.String(255), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", TZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'done', 'failed')",
            name="ck_uploads_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_uploads_project_id_projects", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_uploads"),
        sa.UniqueConstraint("project_id", "checksum", name="uq_uploads_project_id_checksum"),
    )
    op.create_index("ix_uploads_project_id", "uploads", ["project_id"])

    op.create_table(
        "ci_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("ci_run_id", sa.String(255), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("errored", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_ci_runs_project_id_projects", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], ["uploads.id"],
            name="fk_ci_runs_upload_id_uploads", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ci_runs"),
        sa.UniqueConstraint("upload_id", name="uq_ci_runs_upload_id"),
    )
    op.create_index("ix_ci_runs_project_started", "ci_runs", ["project_id", "started_at", "id"])
    op.create_index("ix_ci_runs_project_commit", "ci_runs", ["project_id", "commit_sha"])

    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("suite", sa.String(500), nullable=False),
        sa.Column("classname", sa.String(500), nullable=False),
        sa.Column("name", sa.String(1000), nullable=False),
        sa.Column("file", sa.String(1000), nullable=True),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("first_seen_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_test_cases_project_id_projects", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_cases"),
        sa.UniqueConstraint(
            "project_id", "identity_hash", name="uq_test_cases_project_id_identity_hash"
        ),
    )

    op.create_table(
        "test_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("retried", sa.Boolean(), nullable=False),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'error', 'skipped')",
            name="ck_test_results_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["ci_runs.id"],
            name="fk_test_results_run_id_ci_runs", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id"], ["test_cases.id"],
            name="fk_test_results_test_case_id_test_cases", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_results"),
    )
    op.create_index("ix_test_results_case_run", "test_results", ["test_case_id", "run_id"])
    op.create_index("ix_test_results_run", "test_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("test_results")
    op.drop_table("test_cases")
    op.drop_table("ci_runs")
    op.drop_table("uploads")
    op.drop_table("api_tokens")
    op.drop_table("projects")
