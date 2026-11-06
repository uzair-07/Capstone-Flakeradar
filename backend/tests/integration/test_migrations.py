"""The Alembic migrations must produce exactly the schema the ORM models describe."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db.base import Base
from app.db.session import get_engine

pytestmark = pytest.mark.integration


def test_migrations_match_models():
    with get_engine().connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    assert diff == [], f"Models and migrations differ; add a migration: {diff}"
