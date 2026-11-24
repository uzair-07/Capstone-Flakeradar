"""Simulate CI history for the demo suite and (optionally) upload it to FlakeRadar.

Each simulated commit runs the 60 demo tests once. When a run has failures, CI re-runs it on
the same commit with the given probability, as many teams do, which creates the
"passed and failed on the same commit" evidence the score uses.

    python evaluation/simulate.py --commits 60 --out sim-reports
    python evaluation/simulate.py --commits 60 --server http://localhost:8080 \\
        --project demo --token fr_...        # needs: pip install ./uploader

Standard library only. The same --seed gives the same history.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = json.loads((ROOT / "demo" / "ground_truth.json").read_text())
CLASSNAME = GROUND_TRUTH["classname"]


@dataclass(frozen=True)
class SimulatedRun:
    commit: str
    attempt: int
    started_at: datetime
    results: dict[str, bool]  # test id -> passed

    @property
    def filename(self) -> str:
        return f"{self.started_at:%Y%m%dT%H%M}-{self.commit[:8]}-a{self.attempt}.xml"


def test_id(name: str) -> str:
    """The name pytest gives each parametrised demo test."""
    return f"test_case[{name}]"


def run_suite(rng: random.Random) -> dict[str, bool]:
    return {
        test_id(t["name"]): rng.random() >= t["failure_probability"]
        for t in GROUND_TRUTH["tests"]
    }


def simulate(
    commits: int, rerun_probability: float, seed: int, start: datetime
) -> list[SimulatedRun]:
    rng = random.Random(seed)
    runs: list[SimulatedRun] = []
    when = start
    for index in range(commits):
        commit = f"{rng.getrandbits(160):040x}"
        attempt = 1
        while True:
            results = run_suite(rng)
            runs.append(SimulatedRun(commit, attempt, when, results))
            when += timedelta(minutes=17)
            if all(results.values()) or attempt >= 2 or rng.random() >= rerun_probability:
                break
            attempt += 1
        when += timedelta(hours=3, minutes=index % 7)
    return runs


def to_junit(run: SimulatedRun) -> bytes:
    cases = []
    for name, passed in run.results.items():
        body = "" if passed else '<failure message="Simulated intermittent failure"/>'
        cases.append(
            f"<testcase classname={quoteattr(CLASSNAME)} name={quoteattr(name)} "
            f'time="0.012">{body}</testcase>'
        )
    failures = sum(1 for passed in run.results.values() if not passed)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="demo" tests="{len(run.results)}" failures="{failures}" '
        f'timestamp="{run.started_at.isoformat()}">{"".join(cases)}</testsuite>\n'
    ).encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--commits", type=int, default=60)
    parser.add_argument("--rerun-probability", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--start", default="2026-10-01T08:00:00+00:00")
    parser.add_argument("--out", type=Path, help="Write the reports to this folder")
    parser.add_argument("--server", help="Upload to this FlakeRadar URL")
    parser.add_argument("--project")
    parser.add_argument("--token")
    args = parser.parse_args(argv)

    runs = simulate(
        args.commits, args.rerun_probability, args.seed, datetime.fromisoformat(args.start)
    )
    if not args.out and not args.server:
        parser.error("give --out and/or --server")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for run in runs:
            (args.out / run.filename).write_bytes(to_junit(run))
        print(f"wrote {len(runs)} reports to {args.out}")

    if args.server:
        if not (args.project and args.token):
            parser.error("--server needs --project and --token")
        try:
            from flakeradar_uploader.cli import CiMetadata, UploadError, upload_file
        except ImportError:
            print("error: install the uploader first: pip install ./uploader", file=sys.stderr)
            return 2
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            for i, run in enumerate(runs, 1):
                path = Path(tmp) / run.filename
                path.write_bytes(to_junit(run))
                meta = CiMetadata(run.commit, "main", f"sim-{args.seed}-{i}", run.attempt)
                try:
                    upload_file(args.server, args.project, args.token, str(path), meta)
                except UploadError as exc:
                    print(f"error on {run.filename}: {exc}", file=sys.stderr)
                    return 1
        print(f"uploaded {len(runs)} reports to {args.server} ({args.project})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
