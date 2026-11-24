from datetime import UTC, datetime, timedelta

from app.analytics.scoring import ResultPoint, compute_stats, explain

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def point(i, status, commit=None, branch="main", retried=False):
    return ResultPoint(
        started_at=T0 + timedelta(hours=i),
        status=status,
        commit_sha=commit if commit is not None else f"c{i}",
        branch=branch,
        retried=retried,
    )


def test_always_passing_test_scores_zero():
    stats = compute_stats([point(i, "passed") for i in range(20)])

    assert stats.score == 0
    assert stats.runs == 20 and stats.failures == 0
    assert not stats.suggest_quarantine
    assert explain(stats) == "Passed all 20 recent runs."


def test_consistently_broken_test_is_not_flaky():
    history = [point(i, "passed") for i in range(10)] + [point(i, "failed") for i in range(10, 20)]
    stats = compute_stats(history)

    assert stats.flips == 1
    assert stats.contradiction_commits == 0
    assert stats.score < 0.05  # one transition from a real regression
    assert not stats.suggest_quarantine


def test_same_commit_pass_and_fail_is_strong_evidence():
    history = []
    for i in range(10):  # every commit fails first, then passes on re-run
        history.append(point(2 * i, "failed", commit=f"c{i}"))
        history.append(point(2 * i + 1, "passed", commit=f"c{i}"))
    stats = compute_stats(history)

    assert stats.contradiction_commits == 10
    assert stats.commits == 10
    assert stats.score == 1.0
    assert stats.suggest_quarantine
    assert "same commit 10 times" in stats.reason


def test_alternating_results_raise_flip_rate():
    history = [point(i, "passed" if i % 2 else "failed") for i in range(12)]
    stats = compute_stats(history)

    assert stats.flips == 11
    assert stats.flip_rate == 1.0
    assert stats.score == 0.4  # flips only, every commit different
    assert stats.suggest_quarantine


def test_retried_pass_counts_as_contradiction():
    history = [point(i, "passed") for i in range(10)]
    history[4] = point(4, "passed", retried=True)
    stats = compute_stats(history)

    assert stats.retried_runs == 1
    assert stats.contradiction_commits == 1
    assert stats.score > 0
    assert "needed a retry in 1 run" in stats.reason


def test_skips_are_ignored_and_window_limits_history():
    history = [point(i, "failed") for i in range(5)]  # old failures fall outside the window
    history += [point(i, "skipped") for i in range(5, 10)]
    history += [point(i, "passed") for i in range(10, 40)]
    stats = compute_stats(history, window=30)

    assert stats.runs == 30
    assert stats.failures == 0
    assert stats.last_status == "passed"


def test_feature_branch_flips_do_not_count_toward_flip_rate():
    history = [point(i, "passed" if i % 2 else "failed", branch="feat/x") for i in range(10)]
    stats = compute_stats(history)

    assert stats.flips == 0
    assert stats.score == 0


def test_too_few_runs_are_not_suggested():
    history = [point(0, "failed", commit="a"), point(1, "passed", commit="a")]
    stats = compute_stats(history)

    assert stats.score > 0.15
    assert not stats.suggest_quarantine  # needs at least 10 runs


def test_empty_history():
    stats = compute_stats([])

    assert stats.runs == 0 and stats.score == 0
    assert stats.last_status is None
    assert explain(stats) == "No pass or fail results yet."
