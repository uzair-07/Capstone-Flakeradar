"""Flakiness score v1: explainable signals computed from a test's recent history.

A test is flaky when it passes and fails without a relevant code change. Two signals:

* **Contradictions** (strongest evidence): commits where the same test both passed and
  failed, e.g. a failed CI run that turned green on re-run without any new commit. A result
  marked ``retried`` (the report shows a failed attempt before the pass) also counts.
* **Flip rate**: how often the result alternates between pass and fail, in time order, on
  the default branch. A test broken by a real bug fails consistently and flips rarely.

    score = min(1, 0.6 * contradiction_ratio + 0.4 * flip_rate)

Weights and thresholds are starting values; the evaluation in Sprint 4 tunes them.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

WINDOW = 30  # most recent results considered per test
CONTRADICTION_WEIGHT = 0.6
FLIP_WEIGHT = 0.4
MIN_RUNS_FOR_SUGGESTION = 10
SUGGEST_THRESHOLD = 0.15

PASS = "passed"
FAILURES = frozenset({"failed", "error"})


@dataclass(frozen=True)
class ResultPoint:
    started_at: datetime
    status: str  # passed | failed | error | skipped
    commit_sha: str | None
    branch: str | None
    retried: bool = False


@dataclass(frozen=True)
class FlakinessStats:
    runs: int  # results that passed or failed (skips excluded)
    passes: int
    failures: int
    flips: int
    flip_rate: float
    commits: int
    contradiction_commits: int
    retried_runs: int
    score: float
    last_status: str | None
    last_run_at: datetime | None

    @property
    def failure_rate(self) -> float:
        return self.failures / self.runs if self.runs else 0.0

    @property
    def suggest_quarantine(self) -> bool:
        return self.runs >= MIN_RUNS_FOR_SUGGESTION and self.score >= SUGGEST_THRESHOLD

    @property
    def reason(self) -> str:
        return explain(self)


def compute_stats(
    history: Sequence[ResultPoint], default_branch: str = "main", window: int = WINDOW
) -> FlakinessStats:
    """Score one test from its results. `history` may be in any order."""
    ordered = sorted(history, key=lambda point: point.started_at)
    last = ordered[-1] if ordered else None
    decided = [p for p in ordered if p.status == PASS or p.status in FAILURES][-window:]

    passes = sum(1 for p in decided if p.status == PASS)
    failures = len(decided) - passes
    retried_runs = sum(1 for p in decided if p.retried)

    outcomes_by_commit: dict[str, set[bool]] = defaultdict(set)
    for point in decided:
        if point.commit_sha:
            outcomes_by_commit[point.commit_sha].add(point.status == PASS)
            if point.retried:  # a failed attempt hidden behind the final pass
                outcomes_by_commit[point.commit_sha].add(False)
    contradictions = sum(1 for outcomes in outcomes_by_commit.values() if len(outcomes) == 2)
    commits = len(outcomes_by_commit)
    # Retries without commit information still prove flakiness within one run.
    unattributed_retries = sum(1 for p in decided if p.retried and not p.commit_sha)
    contradiction_ratio = (
        (contradictions + unattributed_retries) / (commits + unattributed_retries)
        if commits + unattributed_retries
        else 0.0
    )

    main_line = [p.status == PASS for p in decided if p.branch in (default_branch, None)]
    flips = sum(1 for a, b in zip(main_line, main_line[1:], strict=False) if a != b)
    flip_rate = flips / (len(main_line) - 1) if len(main_line) > 1 else 0.0

    score = min(1.0, CONTRADICTION_WEIGHT * contradiction_ratio + FLIP_WEIGHT * flip_rate)
    return FlakinessStats(
        runs=len(decided),
        passes=passes,
        failures=failures,
        flips=flips,
        flip_rate=round(flip_rate, 4),
        commits=commits,
        contradiction_commits=contradictions,
        retried_runs=retried_runs,
        score=round(score, 4),
        last_status=last.status if last else None,
        last_run_at=last.started_at if last else None,
    )


def explain(stats: FlakinessStats) -> str:
    """One plain sentence a developer can act on."""
    if stats.runs == 0:
        return "No pass or fail results yet."
    if stats.failures == 0 and stats.retried_runs == 0:
        return f"Passed all {stats.runs} recent runs."
    if stats.passes == 0:
        return f"Failed all {stats.runs} recent runs: likely broken, not flaky."
    parts = []
    if stats.contradiction_commits:
        parts.append(
            f"passed and failed on the same commit {stats.contradiction_commits} "
            f"time{'s' if stats.contradiction_commits != 1 else ''}"
        )
    if stats.retried_runs:
        parts.append(
            f"needed a retry in {stats.retried_runs} run{'s' if stats.retried_runs != 1 else ''}"
        )
    if stats.flips:
        parts.append(f"switched between pass and fail {stats.flips} times on the main branch")
    if not parts:
        return f"Failed {stats.failures} of {stats.runs} recent runs."
    sentence = "; ".join(parts)
    return f"{sentence[0].upper()}{sentence[1:]} ({stats.failures} of {stats.runs} runs failed)."
