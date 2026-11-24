"""Offline accuracy check of the flakiness score against the demo suite's ground truth.

Simulates CI history (see simulate.py), scores every test with the same code the server
uses, and reports precision and recall of "suggested for quarantine".

    python evaluation/evaluate.py --commits 60 --seeds 1 2 3 4 5

Needs only the backend package on the path (no database); run from the repository root.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "evaluation")]

from app.analytics.scoring import ResultPoint, compute_stats  # noqa: E402
from app.ingest.junit import parse_junit_xml  # noqa: E402
from simulate import GROUND_TRUTH, simulate, test_id, to_junit  # noqa: E402

START = datetime.fromisoformat("2026-10-01T08:00:00+00:00")


def evaluate(commits: int, seed: int, rerun_probability: float) -> dict[str, object]:
    history: dict[str, list[ResultPoint]] = defaultdict(list)
    runs = simulate(commits, rerun_probability, seed, START)
    for run in runs:
        report = parse_junit_xml(to_junit(run))  # same parser as the server
        for case in report.test_cases:
            when = report.timestamp or START
            history[case.name].append(
                ResultPoint(when, case.status, run.commit, "main", case.retried)
            )

    truth = {test_id(t["name"]): t["failure_probability"] for t in GROUND_TRUTH["tests"]}
    tp = fp = fn = 0
    found_by_rate: dict[float, list[bool]] = defaultdict(list)
    for name, points in history.items():
        flagged = compute_stats(points).suggest_quarantine
        rate = truth[name]
        if rate > 0:
            found_by_rate[rate].append(flagged)
            tp += flagged
            fn += not flagged
        else:
            fp += flagged
    return {
        "runs": len(runs),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "recall_by_rate": {rate: sum(v) / len(v) for rate, v in sorted(found_by_rate.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the flakiness score offline.")
    parser.add_argument("--commits", type=int, default=60)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--rerun-probability", type=float, default=0.7)
    args = parser.parse_args(argv)

    results = [evaluate(args.commits, seed, args.rerun_probability) for seed in args.seeds]
    print(f"{args.commits} commits per history, {len(results)} seeds, 60 tests (20 flaky)\n")
    print("| Seed | Runs | Flagged correctly | False alarms | Missed | Precision | Recall |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for seed, r in zip(args.seeds, results, strict=True):
        print(
            f"| {seed} | {r['runs']} | {r['tp']} | {r['fp']} | {r['fn']} | "
            f"{r['precision']:.2f} | {r['recall']:.2f} |"
        )
    mean_p = sum(r["precision"] for r in results) / len(results)
    mean_r = sum(r["recall"] for r in results) / len(results)
    print(f"| **Mean** | | | | | **{mean_p:.2f}** | **{mean_r:.2f}** |\n")

    print("Recall by true failure rate:")
    rates = results[0]["recall_by_rate"].keys()
    for rate in rates:
        mean = sum(r["recall_by_rate"][rate] for r in results) / len(results)
        print(f"  {rate:>4.0%} failure rate: {mean:.0%} of tests found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
