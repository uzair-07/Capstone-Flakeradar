"""Run the background worker: ``python -m app.worker``."""

from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker.queue import get_queue, get_redis


def main() -> None:
    configure_logging(get_settings().log_level)
    worker = Worker([get_queue()], connection=get_redis())
    worker.work(with_scheduler=True)  # the scheduler runs delayed retries


if __name__ == "__main__":
    main()
