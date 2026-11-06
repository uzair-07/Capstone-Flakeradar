"""Integration fixtures: a real PostgreSQL schema built by Alembic, and a real Redis queue.

Run locally with the Docker Compose database and queue, using a separate database
(`flakeradar_test`) and Redis database 15. See "Development" in the README.
"""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_engine, session_scope
from app.main import app
from app.projects.service import create_project, create_token
from app.worker.queue import get_redis
from tests.integration.helpers import BACKEND

TABLES = "test_results, test_cases, ci_runs, uploads, api_tokens, projects"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    yield


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    get_redis().flushdb()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def project_token() -> tuple[str, str]:
    """Returns (project slug, plain token)."""
    with session_scope() as db:
        project = create_project(db, "Demo shop", "demo")
        token = create_token(db, project)
        db.commit()
        return project.slug, token.value
