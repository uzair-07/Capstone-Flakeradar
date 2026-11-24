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

from app.db.session import get_engine
from app.main import app
from app.worker.queue import get_redis
from tests.integration.helpers import BACKEND

TABLES = (
    "test_case_stats, test_results, test_cases, ci_runs, uploads, api_tokens, projects, users"
)


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


OWNER = {"email": "owner@example.com", "password": "correct-horse-battery"}


@pytest.fixture
def project_token(client: TestClient) -> tuple[str, str]:
    """Registers and logs in `client`, creates a project and a CI token through the API.

    Returns (project slug, plain token).
    """
    assert client.post("/api/v1/auth/register", json=OWNER).status_code == 201
    created = client.post("/api/v1/projects", json={"name": "Demo shop", "slug": "demo"})
    assert created.status_code == 201, created.text
    token = client.post("/api/v1/projects/demo/tokens", json={"name": "ci"})
    assert token.status_code == 201, token.text
    return "demo", token.json()["token"]
