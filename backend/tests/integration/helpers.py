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
