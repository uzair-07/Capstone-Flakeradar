"""End-to-end through the API, the queue, the worker and PostgreSQL."""

import pytest

from tests.integration.helpers import fixture_bytes, run_worker

pytestmark = pytest.mark.integration

META = {"commit_sha": "3f2c9a1", "branch": "main", "ci_run_id": "1001", "attempt": "1"}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def upload(client, slug, token, name="pytest.xml", content=None, **form):
    return client.post(
        f"/api/v1/projects/{slug}/uploads",
        headers=auth(token),
        files={"file": (name, content if content is not None else fixture_bytes(name))},
        data={**META, **form},
    )


def test_upload_is_parsed_into_a_run(client, project_token):
    slug, token = project_token

    response = upload(client, slug, token)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "received"
    assert body["duplicate"] is False

    run_worker()

    status = client.get(f"/api/v1/uploads/{body['id']}", headers=auth(token))
    assert status.status_code == 200
    assert status.json()["status"] == "done"
    run_id = status.json()["run_id"]
    assert run_id

    runs = client.get(f"/api/v1/projects/{slug}/runs").json()
    assert len(runs["items"]) == 1
    run = runs["items"][0]
    assert run["id"] == run_id
    assert (run["total"], run["passed"], run["failed"], run["errored"], run["skipped"]) == (
        5, 2, 1, 1, 1,
    )
    assert run["commit_sha"] == "3f2c9a1"
    assert run["branch"] == "main"


def test_run_detail_lists_failures_first(client, project_token):
    slug, token = project_token
    upload(client, slug, token)
    run_worker()
    run_id = client.get(f"/api/v1/projects/{slug}/runs").json()["items"][0]["id"]

    detail = client.get(f"/api/v1/runs/{run_id}").json()

    statuses = [result["status"] for result in detail["results"]]
    assert statuses == ["failed", "error", "passed", "passed", "skipped"]
    assert detail["results"][0]["name"] == "test_payment_timeout"
    assert "504" in detail["results"][0]["failure_message"]
    assert detail["project_slug"] == slug


def test_same_file_twice_creates_one_run(client, project_token):
    slug, token = project_token
    first = upload(client, slug, token)
    second = upload(client, slug, token)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["duplicate"] is True
    run_worker()
    assert len(client.get(f"/api/v1/projects/{slug}/runs").json()["items"]) == 1


def test_test_cases_are_shared_between_runs(client, project_token):
    slug, token = project_token
    upload(client, slug, token, ci_run_id="1001")
    content = fixture_bytes("pytest.xml").replace(b"runner-1", b"runner-2")  # new checksum
    upload(client, slug, token, content=content, ci_run_id="1002")
    run_worker()

    runs = client.get(f"/api/v1/projects/{slug}/runs").json()["items"]
    assert len(runs) == 2
    first, second = (client.get(f"/api/v1/runs/{run['id']}").json() for run in runs)
    assert {r["test_case_id"] for r in first["results"]} == {
        r["test_case_id"] for r in second["results"]
    }


def test_invalid_report_fails_with_reason(client, project_token):
    slug, token = project_token
    body = upload(client, slug, token, name="malformed.xml").json()
    run_worker()

    status = client.get(f"/api/v1/uploads/{body['id']}", headers=auth(token))
    assert status.json()["status"] == "failed"
    assert "not valid XML" in status.json()["error"]
    assert client.get(f"/api/v1/projects/{slug}/runs").json()["items"] == []


def test_missing_or_wrong_token_is_rejected(client, project_token):
    slug, _ = project_token
    no_token = client.post(
        f"/api/v1/projects/{slug}/uploads", files={"file": ("r.xml", b"<testsuite/>")}
    )
    assert no_token.status_code == 401
    assert no_token.headers["content-type"].startswith("application/problem+json")
    assert no_token.json()["request_id"]

    wrong = upload(client, slug, "fr_00000000_not-a-real-token")
    assert wrong.status_code == 401


def test_token_from_another_project_is_forbidden(client, project_token):
    from app.db.session import session_scope
    from app.projects.service import create_project, create_token

    slug, _ = project_token
    with session_scope() as db:
        other = create_project(db, "Other", "other")
        other_token = create_token(db, other).value
        db.commit()

    assert upload(client, slug, other_token).status_code == 403


def test_oversized_upload_is_rejected(client, project_token, monkeypatch):
    from app.core.config import get_settings

    slug, token = project_token
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    response = upload(client, slug, token)

    assert response.status_code == 413
    assert "at most" in response.json()["detail"]


def test_unknown_project_is_404(client, project_token):
    _, token = project_token
    assert upload(client, "no-such-project", token).status_code == 404


def test_runs_pagination(client, project_token):
    slug, token = project_token
    for n in range(3):
        content = fixture_bytes("pytest.xml").replace(b"runner-1", f"runner-x{n}".encode())
        content = content.replace(b"14:02:11", f"14:0{n}:00".encode())
        upload(client, slug, token, content=content, ci_run_id=str(n))
    run_worker()

    page1 = client.get(f"/api/v1/projects/{slug}/runs", params={"limit": 2}).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = client.get(
        f"/api/v1/projects/{slug}/runs", params={"limit": 2, "cursor": page1["next_cursor"]}
    ).json()
    assert len(page2["items"]) == 1 and page2["next_cursor"] is None
    ids = [r["ci_run_id"] for r in page1["items"] + page2["items"]]
    assert ids == ["2", "1", "0"]  # newest first


def test_health_endpoints(client):
    assert client.get("/healthz").json()["status"] == "ok"
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": "ok", "queue": "ok"}
