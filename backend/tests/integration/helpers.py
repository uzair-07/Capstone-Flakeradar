from pathlib import Path

from rq import SimpleWorker

from app.worker.queue import get_queue, get_redis

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures" / "junit"


def run_worker() -> None:
    """Process every queued job in this process, then return."""
    SimpleWorker([get_queue()], connection=get_redis()).work(burst=True)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def junit_report(results: dict[str, str], timestamp: str) -> bytes:
    """A minimal JUnit report: {test name: "passed" | "failed"} in class tests.test_demo."""
    cases = []
    for name, status in results.items():
        body = '<failure message="boom"/>' if status == "failed" else ""
        cases.append(
            f'<testcase classname="tests.test_demo" name="{name}" time="0.1">{body}</testcase>'
        )
    return (
        f'<testsuite name="demo" timestamp="{timestamp}">{"".join(cases)}</testsuite>'
    ).encode()
