"""Accounts, project access, token management and flakiness scores end to end."""

import pytest

from tests.integration.conftest import OWNER
from tests.integration.helpers import junit_report, run_worker

pytestmark = pytest.mark.integration


def upload(client, token, content, commit, attempt=1):
    return client.post(
        "/api/v1/projects/demo/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("report.xml", content)},
        data={"commit_sha": commit, "branch": "main", "attempt": str(attempt)},
    )


def test_register_login_logout(client):
    created = client.post("/api/v1/auth/register", json=OWNER)
    assert created.status_code == 201
    assert created.json()["email"] == OWNER["email"]
    assert "password" not in created.text
    assert client.get("/api/v1/auth/me").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    wrong = client.post("/api/v1/auth/login", json={**OWNER, "password": "wrong-password-1"})
    assert wrong.status_code == 401
    assert client.post("/api/v1/auth/login", json=OWNER).status_code == 200
    assert client.get("/api/v1/auth/me").json()["email"] == OWNER["email"]


def test_registration_rules(client):
    assert client.post("/api/v1/auth/register", json=OWNER).status_code == 201
    assert client.post("/api/v1/auth/register", json=OWNER).status_code == 409
    short = client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "short"})
    assert short.status_code == 400
    bad_email = client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "long-enough-pw"}
    )
    assert bad_email.status_code == 400


def test_runs_need_login_and_ownership(client, project_token):
    assert client.get("/api/v1/projects/demo/runs").status_code == 200

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/projects/demo/runs").status_code == 401

    other = {"email": "other@example.com", "password": "another-long-password"}
    assert client.post("/api/v1/auth/register", json=other).status_code == 201
    assert client.get("/api/v1/projects/demo/runs").status_code == 404
    assert client.get("/api/v1/projects").json() == []


def test_tokens_are_listed_without_secret_and_can_be_revoked(client, project_token):
    _, token = project_token
    listed = client.get("/api/v1/projects/demo/tokens").json()
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert token.startswith(f"fr_{listed[0]['prefix']}_")

    report = junit_report({"test_a": "passed"}, "2026-11-20T10:00:00")
    assert upload(client, token, report, "c1").status_code == 202

    revoked = client.delete(f"/api/v1/projects/demo/tokens/{listed[0]['id']}")
    assert revoked.status_code == 204
    report2 = junit_report({"test_a": "passed"}, "2026-11-20T11:00:00")
    assert upload(client, token, report2, "c2").status_code == 401


def test_duplicate_project_slug_is_a_conflict(client, project_token):
    again = client.post("/api/v1/projects", json={"name": "Demo again", "slug": "demo"})
    assert again.status_code == 409


def test_flaky_test_ranks_first_with_a_reason(client, project_token):
    _, token = project_token
    # 12 commits. test_flaky fails on the first attempt and passes on the re-run of every
    # third commit; test_stable always passes; test_broken fails from commit 6 onwards.
    hour = 0
    for commit in range(12):
        attempts = 2 if commit % 3 == 0 else 1
        for attempt in range(1, attempts + 1):
            flaky = "failed" if (commit % 3 == 0 and attempt == 1) else "passed"
            broken = "failed" if commit >= 6 else "passed"
            report = junit_report(
                {"test_flaky": flaky, "test_stable": "passed", "test_broken": broken},
                f"2026-11-{10 + hour // 24:02d}T{hour % 24:02d}:00:00",
            )
            assert upload(client, token, report, f"commit{commit}", attempt).status_code == 202
            hour += 1
    run_worker()

    page = client.get("/api/v1/projects/demo/tests").json()
    assert page["total"] == 3
    by_name = {item["name"]: item for item in page["items"]}
    assert page["items"][0]["name"] == "test_flaky"

    flaky = by_name["test_flaky"]
    assert flaky["contradiction_commits"] == 4
    assert flaky["suggest_quarantine"] is True
    assert "same commit 4 times" in flaky["reason"]

    assert by_name["test_stable"]["score"] == 0
    assert by_name["test_broken"]["score"] < flaky["score"]
    assert by_name["test_broken"]["suggest_quarantine"] is False

    only_flaky = client.get("/api/v1/projects/demo/tests", params={"flaky_only": True}).json()
    assert [item["name"] for item in only_flaky["items"]] == ["test_flaky"]

    detail = client.get(f"/api/v1/tests/{flaky['id']}").json()
    assert len(detail["history"]) == 16  # 12 commits + 4 re-runs
    assert detail["history"][0]["started_at"] > detail["history"][-1]["started_at"]
