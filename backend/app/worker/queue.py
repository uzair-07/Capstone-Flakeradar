from functools import lru_cache

from redis import Redis
from rq import Queue, Retry

from app.core.config import get_settings

PROCESS_UPLOAD = "app.worker.jobs.process_upload"


@lru_cache
def get_redis() -> Redis:
    # No socket read timeout: the worker blocks on the queue for long periods.
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=3)


@lru_cache
def get_health_redis() -> Redis:
    """Short timeouts so /readyz answers quickly when Redis is down."""
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)


def get_queue() -> Queue:
    return Queue(get_settings().queue_name, connection=get_redis())


def enqueue_upload(upload_id: str) -> None:
    get_queue().enqueue(
        PROCESS_UPLOAD,
        upload_id,
        job_id=f"upload-{upload_id}",  # the same upload is never queued twice
        retry=Retry(max=3, interval=[5, 30, 120]),
        job_timeout=300,
        result_ttl=3600,
        failure_ttl=7 * 24 * 3600,
    )
