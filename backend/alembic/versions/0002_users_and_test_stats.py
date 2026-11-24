"""Users, project owners and per-test flakiness statistics.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.add_column("projects", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_projects_owner_id_users", "projects", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    op.create_table(
        "test_case_stats",
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False),
        sa.Column("passes", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("flips", sa.Integer(), nullable=False),
        sa.Column("flip_rate", sa.Double(), nullable=False),
        sa.Column("commits", sa.Integer(), nullable=False),
        sa.Column("contradiction_commits", sa.Integer(), nullable=False),
        sa.Column("retried_runs", sa.Integer(), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("last_status", sa.String(10), nullable=True),
        sa.Column("last_run_at", TZ, nullable=True),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_case_id"], ["test_cases.id"],
            name="fk_test_case_stats_test_case_id_test_cases", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_test_case_stats_project_id_projects", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("test_case_id", name="pk_test_case_stats"),
    )
    op.create_index(
        "ix_test_case_stats_project_score", "test_case_stats", ["project_id", "score"]
    )


def downgrade() -> None:
    op.drop_table("test_case_stats")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_constraint("fk_projects_owner_id_users", "projects", type_="foreignkey")
    op.drop_column("projects", "owner_id")
    op.drop_table("users")
